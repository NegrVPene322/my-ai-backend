import os
import threading
import requests
from gtts import gTTS
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from dotenv import load_dotenv
import tempfile
import speech_recognition as sr

# Загружаем переменные окружения
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL")

if not BACKEND_URL:
    raise ValueError("BACKEND_URL не указан в .env")


class ChatApp(App):
    def build(self):
        self.title = "Qwen Chat"
        self.messages = []
        self.layout = BoxLayout(orientation='vertical')

        # Чат с прокруткой
        self.chat_layout = GridLayout(cols=1, size_hint_y=None)
        self.chat_layout.bind(minimum_height=self.chat_layout.setter('height'))
        self.scroll = ScrollView(size_hint=(1, 0.8))
        self.scroll.add_widget(self.chat_layout)
        self.layout.add_widget(self.scroll)

        # Поле ввода и кнопки
        input_layout = BoxLayout(size_hint=(1, 0.1))
        self.input = TextInput(hint_text="Введите сообщение...", multiline=False, font_size=16)
        self.input.bind(on_text_validate=self.send_text)
        send_btn = Button(text="📤", size_hint=(0.2, 1), font_size=16)
        send_btn.bind(on_press=self.send_text)
        voice_btn = Button(text="🎤", size_hint=(0.2, 1), font_size=16)
        voice_btn.bind(on_press=self.start_voice_input)

        input_layout.add_widget(self.input)
        input_layout.add_widget(send_btn)
        input_layout.add_widget(voice_btn)
        self.layout.add_widget(input_layout)

        return self.layout

    def add_message(self, text, is_user=False):
        color = (0, 0, 1, 0.2) if is_user else (0, 1, 0, 0.2)  # синий / зелёный
        label = Label(
            text=text,
            size_hint_y=None,
            text_size=(self.layout.width * 0.8, None),
            halign='right' if is_user else 'left',
            valign='middle',
            padding=(10, 10),
            color=(0, 0, 0, 1)
        )
        label.bind(texture_size=label.setter('size'))
        with label.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*color)
            rect = Rectangle(pos=label.pos, size=label.size)
            label.bind(pos=lambda *args: setattr(rect, 'pos', args[1]), size=lambda *args: setattr(rect, 'size', args[1]))
        self.chat_layout.add_widget(label)
        self.scroll.scroll_to(label)

    def speak_text(self, text):
        """Озвучка через gtts + Kivy SoundLoader (безопасно)"""
        try:
            tts = gTTS(text=text, lang='ru')
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            tts.save(temp_file.name)
            temp_file.close()

            def play_sound(dt):
                try:
                    sound = SoundLoader.load(temp_file.name)
                    if sound:
                        sound.play()
                        def cleanup(dt2):
                            try:
                                os.unlink(temp_file.name)
                            except:
                                pass
                        Clock.schedule_once(cleanup, sound.length + 1)
                except Exception as ex:
                    print("Ошибка воспроизведения:", ex)
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
            Clock.schedule_once(play_sound, 0)
        except Exception as ex:
            print("Ошибка TTS:", ex)

    def start_voice_input(self, instance):
        self.add_message("🎙️ Слушаю...", is_user=True)
        threading.Thread(target=self.listen_and_recognize, daemon=True).start()

    def listen_and_recognize(self):
        r = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=3, phrase_time_limit=8)
                text = r.recognize_google(audio, language="ru-RU")
                def ui_update(dt):
                    if self.chat_layout.children and "Слушаю..." in self.chat_layout.children[0].text:
                        self.chat_layout.remove_widget(self.chat_layout.children[0])
                    self.input.text = text
                    self.send_text(None)
                Clock.schedule_once(ui_update, 0)
        except sr.WaitTimeoutError:
            self.handle_voice_error("Время ожидания истекло")
        except sr.UnknownValueError:
            self.handle_voice_error("Не удалось распознать речь")
        except sr.RequestError as e:
            self.handle_voice_error(f"Ошибка сервиса: {e}")
        except OSError as e:
            if "not found" in str(e).lower():
                self.handle_voice_error("Микрофон не найден")
            else:
                self.handle_voice_error(f"Ошибка микрофона: {e}")
        except Exception as e:
            self.handle_voice_error(f"Ошибка: {e}")

    def handle_voice_error(self, message):
        def ui_error(dt):
            if self.chat_layout.children and "Слушаю..." in self.chat_layout.children[0].text:
                self.chat_layout.remove_widget(self.chat_layout.children[0])
            self.add_message(f"🎙️ {message}", is_user=True)
        Clock.schedule_once(ui_error, 0)

    def send_text(self, instance):
        user_text = self.input.text.strip()
        if not user_text:
            return
        self.input.text = ""
        self.add_message(user_text, is_user=True)
        self.add_message("...", is_user=False)
        last_message = self.chat_layout.children[0]

        def get_ai_response():
            try:
                response = requests.post(
                    f"{BACKEND_URL}/chat",
                    json={"messages": [{"role": "user", "content": user_text}]},
                    timeout=60
                )
                response.raise_for_status()
                ai_text = response.json()["reply"]

                def update_ui(dt):
                    try:
                        self.chat_layout.remove_widget(last_message)
                    except:
                        pass
                    self.add_message(ai_text, is_user=False)
                    self.speak_text(ai_text)
                Clock.schedule_once(update_ui, 0)
            except Exception as e:
                error_msg = str(e)
                if "Read timed out" in error_msg:
                    error_msg = "❌ Таймаут: сервер не ответил за 60 секунд"
                def show_error(dt):
                    try:
                        self.chat_layout.remove_widget(last_message)
                    except:
                        pass
                    self.add_message(f"❌ Ошибка: {error_msg}", is_user=False)
                Clock.schedule_once(show_error, 0)

        threading.Thread(target=get_ai_response, daemon=True).start()


if __name__ == "__main__":
    ChatApp().run()