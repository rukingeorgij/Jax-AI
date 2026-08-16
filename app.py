import json
import os
import re
import requests
import logging
from datetime import datetime
from openai import OpenAI
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from getpass import getpass

app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JaxAI:
    def __init__(self):
        self.name = "Джекс"
        self.icon = "🤖"
        self.version = "5.4"
        
        # СКРЫТЫЙ КЛЮЧ: читаем из файла или спрашиваем при запуске
        api_key = self.get_api_key()
        
        self.chats_file = "jax_chats.json"
        self.learning_file = "jax_learning.json"
        
        self.chats = self.load_data(self.chats_file, {})
        self.learning = self.load_data(self.learning_file, {})
        
        self.current_chat_id = "1"
        self.current_chat_history = self.chats.get("1", [])
        
        self.search_triggers = [
            "сколько", "когда", "где", "почему", "как", "что такое",
            "кто такой", "в каком году", "какой", "чем", "зачем",
            "что значит", "что это", "расскажи про", "история",
            "биография", "факты", "информация"
        ]
        
        self.cache = {}
        self.cache_timeout = 300
        
        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
                timeout=30
            )
            self.model = "llama-3.3-70b-versatile"
            print("✅ Нейросеть подключена!")
        except Exception as e:
            print(f"⚠️ Ошибка подключения: {e}")
            self.client = None
            self.model = None
    
    def get_api_key(self):
        """Получение ключа из скрытого файла или запрос у пользователя"""
        
        # Вариант 1: Из файла secret.key (если существует)
        secret_file = "secret.key"
        if os.path.exists(secret_file):
            try:
                with open(secret_file, 'r') as f:
                    key = f.read().strip()
                    if key:
                        return key
            except:
                pass
        
        # Вариант 2: Из переменной окружения
        env_key = os.getenv("GROQ_API_KEY")
        if env_key:
            return env_key
        
        # Вариант 3: Спросить при первом запуске
        print("\n" + "=" * 50)
        print("🔑 Первый запуск! Введи свой API ключ:")
        print("(Он сохранится в secret.key и больше не спросит)")
        print("=" * 50)
        
        key = getpass("API ключ: ").strip()
        
        if key:
            # Сохраняем в скрытый файл
            try:
                with open(secret_file, 'w') as f:
                    f.write(key)
                # Пытаемся скрыть файл
                os.chmod(secret_file, 0o600)  # Только владелец может читать
                print("✅ Ключ сохранен!")
            except:
                pass
        
        return key
    
    def load_data(self, filename, default):
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return default
    
    def save_data(self, data, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def search_internet(self, query):
        try:
            url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            results = []
            if "AbstractText" in data and data["AbstractText"]:
                results.append(data["AbstractText"])
            
            for topic in data.get("RelatedTopics", [])[:2]:
                if "Text" in topic:
                    results.append(topic["Text"])
            
            return results[:2] if results else None
        except:
            return None
    
    def get_weather(self, city):
        cache_key = f"weather_{city}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.cache_timeout:
                return cached_data
        
        try:
            url = f"https://wttr.in/{city}?format=j1&lang=ru"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            current = data["current_condition"][0]
            temp = current["temp_C"]
            desc = current["lang_ru"][0]["value"]
            
            result = f"🌡️ {city.capitalize()}: {temp}°C, {desc}"
            self.cache[cache_key] = (datetime.now(), result)
            
            return result
        except:
            return f"Не удалось получить погоду для {city}"
    
    def get_news(self):
        if "news" in self.cache:
            cached_time, cached_data = self.cache["news"]
            if (datetime.now() - cached_time).seconds < self.cache_timeout:
                return cached_data
        
        try:
            url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=2"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            news_list = []
            for article in data.get("results", [])[:2]:
                title = article.get("title", "")
                news_list.append(f"📰 {title}")
            
            result = "\n".join(news_list) if news_list else "Нет новостей"
            self.cache["news"] = (datetime.now(), result)
            
            return result
        except:
            return "Не удалось получить новости"
    
    def check_inappropriate(self, text):
        if not self.client:
            return False
        
        try:
            result = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты модератор. Определи, содержит ли текст запрещенный контент (18+, порнография, сексуальный контекст). "
                            "Отвечай только 'YES' или 'NO'. "
                            "YES - если контекст действительно неприемлемый. "
                            "NO - если текст нормальный."
                        )
                    },
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                max_tokens=5,
                timeout=5
            )
            
            answer = result.choices[0].message.content.strip().upper()
            return answer == "YES"
        except:
            return False
    
    def validate_images(self, images):
        if images is None or len(images) == 0:
            return True, ""
        
        if len(images) > 10:
            return False, "Максимум 10 фото!"
        
        for img in images:
            if not img or not img.startswith('data:image/'):
                return False, "Это не изображение!"
            
            if len(img) > 10 * 1024 * 1024:
                return False, "Фото слишком большое!"
        
        return True, ""
    
    def extract_city(self, text):
        text_lower = text.lower()
        
        if " в " in text_lower:
            parts = text_lower.split(" в ", 1)
            if len(parts) > 1:
                words = parts[1].split()
                if words:
                    return words[0].rstrip("?,.!")
        
        return None
    
    def should_search(self, text):
        text_lower = text.lower()
        return any(trigger in text_lower for trigger in self.search_triggers)
    
    def generate_response(self, user_input, images=None):
        valid, error = self.validate_images(images)
        if not valid:
            return error
        
        if self.check_inappropriate(user_input):
            return "Извини, но я не могу обсуждать эту тему."
        
        user_lower = user_input.lower()
        
        if images and len(images) > 0:
            return f"📸 Получил {len(images)} фото. Анализ скоро будет!"
        
        if "погода" in user_lower:
            city = self.extract_city(user_input)
            return self.get_weather(city) if city else "Какой город?"
        
        if "новости" in user_lower:
            return self.get_news()
        
        internet_results = None
        if self.should_search(user_input):
            internet_results = self.search_internet(user_input)
        
        if self.client and self.model:
            try:
                system_content = (
                    "Ты Джекс - умный ИИ. "
                    "Отвечай быстро и по делу. "
                    "Понимай опечатки. "
                    "Создатель: Георгий. "
                    "Не раскрывай личные данные. "
                    "Не отвечай на 18+."
                )
                
                if internet_results:
                    system_content += f"\n\nИнфа из инета:\n{' | '.join(internet_results[:1])}"
                
                messages = [{"role": "system", "content": system_content}]
                
                for entry in self.current_chat_history[-5:]:
                    messages.append({"role": "user", "content": entry["user"]})
                    messages.append({"role": "assistant", "content": entry["response"]})
                
                messages.append({"role": "user", "content": user_input})
                
                result = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.5,
                    max_tokens=300,
                    timeout=15
                )
                
                response = result.choices[0].message.content.strip()
                
            except Exception as e:
                response = "Произошла ошибка. Попробуй еще раз."
        else:
            response = "Оффлайн."
        
        self.current_chat_history.append({
            "user": user_input,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
        
        if len(self.current_chat_history) > 100:
            self.current_chat_history = self.current_chat_history[-100:]
        
        self.chats[self.current_chat_id] = self.current_chat_history
        self.save_data(self.chats, self.chats_file)
        
        return response

jax = JaxAI()

def my_smart_ai(user_text, images=None):
    return jax.generate_response(user_text, images)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Джекс</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0b0b0b; color: #f5f5f5; font-family: -apple-system, sans-serif; height: 100vh; display: flex; flex-direction: column; }
        header { padding: 15px; background: #141414; border-bottom: 1px solid #222; text-align: center; }
        #chat { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; }
        .msg { max-width: 80%; padding: 10px 14px; border-radius: 12px; word-wrap: break-word; }
        .user { background: #ff6b35; color: #000; align-self: flex-end; }
        .ai { background: #222; align-self: flex-start; border: 1px solid #333; }
        .input-area { padding: 10px; background: #141414; border-top: 1px solid #222; }
        .input-row { display: flex; gap: 8px; }
        #userInput { flex: 1; padding: 12px; border-radius: 20px; border: 1px solid #333; background: #202020; color: #fff; outline: none; }
        .btn { width: 40px; height: 40px; border-radius: 50%; border: none; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; }
        .send { background: #ff6b35; color: #000; }
        .photo { background: #333; color: #ff6b35; }
        .preview { display: flex; gap: 5px; margin-bottom: 5px; flex-wrap: wrap; }
        .preview img { width: 50px; height: 50px; object-fit: cover; border-radius: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <header>🤖 Джекс v5.4</header>
    <div id="chat">
        <div class="msg ai">Привет! Я Джекс. Спрашивай!</div>
    </div>
    <div class="input-area">
        <div class="preview" id="preview"></div>
        <div class="input-row">
            <input type="file" id="fileInput" accept="image/*" multiple style="display:none">
            <button class="btn photo" onclick="document.getElementById('fileInput').click()">📷</button>
            <input type="text" id="userInput" placeholder="Сообщение..." onkeypress="if(event.key==='Enter') send()">
            <button class="btn send" onclick="send()">➔</button>
        </div>
    </div>
    <script>
        let images = [];
        
        document.getElementById('fileInput').onchange = function(e) {
            for(let file of e.target.files) {
                if(images.length >= 10) { alert('Максимум 10 фото!'); break; }
                const reader = new FileReader();
                reader.onload = function(ev) {
                    images.push(ev.target.result);
                    updatePreview();
                };
                reader.readAsDataURL(file);
            }
        };
        
        function updatePreview() {
            const p = document.getElementById('preview');
            p.innerHTML = '';
            images.forEach((img, i) => {
                p.innerHTML += `<img src="${img}" onclick="images.splice(${i},1); updatePreview()">`;
            });
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        async function send() {
            const input = document.getElementById('userInput');
            const chat = document.getElementById('chat');
            const text = input.value.trim();
            
            if(!text && images.length === 0) return;
            
            let html = '';
            if(images.length > 0) {
                images.forEach(img => { html += `<img src="${img}" style="width:40px;height:40px;border-radius:5px;margin:2px">`; });
            }
            
            chat.innerHTML += `<div class="msg user">${html}${escapeHtml(text)}</div>`;
            input.value = '';
            chat.scrollTop = chat.scrollHeight;
            
            try {
                const res = await fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: text, images: images})
                });
                const data = await res.json();
                chat.innerHTML += `<div class="msg ai">${escapeHtml(data.reply)}</div>`;
            } catch(e) {
                chat.innerHTML += `<div class="msg ai">Ошибка</div>`;
            }
            
            images = [];
            updatePreview();
            chat.scrollTop = chat.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'reply': 'Некорректный запрос'}), 400
        
        user_message = data.get('text', '')[:1000]
        images = data.get('images', [])
        
        if len(images) > 10:
            return jsonify({'reply': 'Максимум 10 фото'}), 400
        
        ai_reply = my_smart_ai(user_message, images)
        return jsonify({'reply': ai_reply})
    except Exception as e:
        logger.error(f"Ошибка в /ask: {e}")
        return jsonify({'reply': 'Внутренняя ошибка сервера'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
