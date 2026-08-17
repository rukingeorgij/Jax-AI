import json
import os
import re
import requests
import logging
import base64
from datetime import datetime, timedelta
from openai import OpenAI
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JaxAI:
    def __init__(self):
        self.name = "Джекс"
        self.version = "1.01"
        
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
        
        self.swear_words = [
            "нахуй", "на хуй", "похуй", "по хуй", "ебать", "бля", "блять",
            "сука", "пиздец", "хуйня", "херня", "охуел", "офигел",
            "заебал", "дохуя", "нихуя"
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
            logger.info("✅ Нейросеть подключена!")
        except Exception as e:
            logger.error(f"⚠️ Ошибка подключения: {e}")
            self.client = None
            self.model = None
    
    def get_api_key(self):
        if os.path.exists("secret.key"):
            try:
                with open("secret.key", "r") as f:
                    key = f.read().strip()
                    if key:
                        return key
            except:
                pass
        
        encrypted = "Z3NrX2o3REZtSkh1Z0RQenRuTGVJdTBXR2R5YjNGWVZrVlluUFJIeGRzSmhjQnZGZldNMUpS"
        
        try:
            key = base64.b64decode(encrypted).decode('utf-8')
            try:
                with open("secret.key", "w") as f:
                    f.write(key)
                os.chmod("secret.key", 0o600)
            except:
                pass
            return key
        except:
            return ""
    
    def load_data(self, filename, default):
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки {filename}: {e}")
        return default
    
    def save_data(self, data, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения {filename}: {e}")
    
    def search_internet(self, query):
        all_results = []
        
        try:
            url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if "AbstractText" in data and data["AbstractText"]:
                all_results.append(data["AbstractText"])
            
            for topic in data.get("RelatedTopics", [])[:3]:
                if "Text" in topic:
                    all_results.append(topic["Text"])
        except Exception as e:
            logger.error(f"Ошибка DuckDuckGo: {e}")
        
        try:
            wiki_url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{query}"
            wiki_response = requests.get(wiki_url, timeout=5)
            wiki_data = wiki_response.json()
            
            if "extract" in wiki_data:
                all_results.append(wiki_data["extract"])
        except Exception as e:
            logger.error(f"Ошибка Wikipedia: {e}")
        
        unique_results = list(set(all_results))
        return unique_results[:5] if unique_results else None
    
    def get_weather(self, city):
        cache_key = f"weather_{city}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if datetime.now() - cached_time < timedelta(seconds=self.cache_timeout):
                return cached_data
        
        try:
            url = f"https://wttr.in/{city}?format=j1&lang=ru"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            # ИСПРАВЛЕНО: правильный путь к данным
            current = data["current_condition"][0]
            temp = current["temp_C"]
            desc = current["lang_ru"][0]["value"]
            
            result = f"🌡️ {city.capitalize()}: {temp}°C, {desc}"
            self.cache[cache_key] = (datetime.now(), result)
            
            return result
        except Exception as e:
            logger.error(f"Ошибка погоды: {e}")
            return f"Не удалось получить погоду для {city}"
    
    def get_news(self):
        if "news" in self.cache:
            cached_time, cached_data = self.cache["news"]
            if datetime.now() - cached_time < timedelta(seconds=self.cache_timeout):
                return cached_data
        
        try:
            url = "https://api.spaceflightnewsapi.net/v4/articles/?limit=3"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            news_list = []
            for article in data.get("results", [])[:3]:
                title = article.get("title", "")
                news_list.append(f"📰 {title}")
            
            result = "\n".join(news_list) if news_list else "Нет новостей"
            self.cache["news"] = (datetime.now(), result)
            
            return result
        except Exception as e:
            logger.error(f"Ошибка новостей: {e}")
            return "Не удалось получить новости"
    
    def is_just_swearing(self, text):
        text_lower = text.lower()
        has_swear = any(word in text_lower for word in self.swear_words)
        
        explicit_words = ["секс", "порно", "член", "пизда", "минет", "куни", "эротика"]
        has_explicit = any(word in text_lower for word in explicit_words)
        
        if has_swear and not has_explicit:
            return True
        
        return False
    
    def check_inappropriate(self, text):
        if not self.client:
            return False
        
        if self.is_just_swearing(text):
            return False
        
        try:
            result = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты модератор. Определи, содержит ли текст ЗАПРЕЩЕННЫЙ контент (18+, порнография, сексуальный контекст). "
                            "Просто маты и ругательства - это НЕ запрещенный контент. "
                            "Отвечай только 'YES' или 'NO'. "
                            "YES - только если есть реальный 18+ контент. "
                            "NO - если это просто мат, ругательства или нормальный текст."
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
        except Exception as e:
            logger.error(f"Ошибка модерации: {e}")
            return False
    
    def validate_images(self, images):
        if images is None:
            return True, ""
        
        if not isinstance(images, list):
            return False, "Некорректные данные фото!"
        
        if len(images) == 0:
            return True, ""
        
        if len(images) > 10:
            return False, "Максимум 10 фото!"
        
        for img in images:
            if not isinstance(img, str) or len(img) > 10 * 1024 * 1024:
                return False, "Фото слишком большое!"
        
        return True, ""
    
    def extract_city(self, text):
        text_lower = text.lower()
        
        if " в " in text_lower:
            parts = text_lower.split(" в ", 1)
            if len(parts) > 1:
                words = parts[1].split()
                if words:
                    city = words[0].rstrip("?,.!")
                    # ИСПРАВЛЕНО: не удаляем буквы, просто возвращаем как есть
                    return city
        
        return None
    
    def should_search(self, text):
        if not text or not text.strip():
            return False
        text_lower = text.lower()
        return any(trigger in text_lower for trigger in self.search_triggers)
    
    def generate_response(self, user_input, images=None):
        # ИСПРАВЛЕНО: проверка на пробелы
        if not user_input or not user_input.strip():
            if not images:
                return "Напиши что-нибудь!"
        
        valid, error = self.validate_images(images)
        if not valid:
            return error
        
        if self.check_inappropriate(user_input or ""):
            return "Извини, но я не могу обсуждать эту тему."
        
        user_lower = (user_input or "").lower()
        
        if images and len(images) > 0:
            return f"📸 Получил {len(images)} фото. Анализ скоро будет!"
        
        if "погода" in user_lower:
            city = self.extract_city(user_input)
            return self.get_weather(city) if city else "Какой город?"
        
        if "новости" in user_lower:
            return self.get_news()
        
        internet_results = None
        if self.should_search(user_input or ""):
            internet_results = self.search_internet(user_input)
        
        if self.client and self.model:
            try:
                system_content = (
                    "Ты Джекс - умный ИИ. "
                    "Отвечай быстро и по делу. "
                    "Создатель: Георгий. "
                    "Используй смайлики ОЧЕНЬ редко."
                )
                
                if internet_results:
                    system_content += f"\n\nИнфа из источников:\n{' | '.join(internet_results[:3])}"
                
                messages = [{"role": "system", "content": system_content}]
                
                for entry in self.current_chat_history[-5:]:
                    # ИСПРАВЛЕНО: пропускаем пустые сообщения
                    if entry.get("user") and entry.get("response"):
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
                logger.error(f"Ошибка генерации: {e}")
                response = "Ошибка. Попробуй еще раз."
        else:
            response = "Оффлайн."
        
        self.current_chat_history.append({
            "user": user_input,
            "response": response
        })
        
        if len(self.current_chat_history) > 100:
            self.current_chat_history = self.current_chat_history[-100:]
        
        self.chats[self.current_chat_id] = self.current_chat_history
        self.save_data(self.chats, self.chats_file)
        
        return response

jax = JaxAI()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Джекс</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0a0a0a; color: #fff; font-family: Arial; height: 100vh; display: flex; flex-direction: column; }
        
        header { display: flex; justify-content: space-between; align-items: center; padding: 10px 15px; background: #111; }
        .menu-btn { background: none; border: none; color: #ff6b35; font-size: 24px; cursor: pointer; }
        .new-chat-btn { background: #ff6b35; border: none; color: #fff; width: 35px; height: 35px; border-radius: 50%; font-size: 20px; cursor: pointer; }
        
        #chat { flex: 1; overflow-y: auto; padding: 15px; }
        .msg { padding: 10px 14px; margin: 5px 0; border-radius: 12px; max-width: 80%; word-wrap: break-word; }
        .user { background: #333; color: #fff; margin-left: auto; }
        .ai { background: #ff6b35; color: #fff; margin-right: auto; }
        
        .input-area { padding: 10px; background: #111; }
        .input-row { display: flex; gap: 8px; align-items: center; }
        .photo-btn { background: #333; border: none; color: #ff6b35; width: 40px; height: 40px; border-radius: 50%; font-size: 20px; cursor: pointer; }
        input { flex: 1; padding: 12px; border-radius: 20px; border: 1px solid #333; background: #222; color: #fff; outline: none; maxlength: 1000; }
        .send-btn { background: #ff6b35; border: none; color: #fff; width: 40px; height: 40px; border-radius: 50%; font-size: 18px; cursor: pointer; }
        
        .preview { display: flex; gap: 5px; margin-bottom: 5px; flex-wrap: wrap; }
        .preview img { width: 50px; height: 50px; object-fit: cover; border-radius: 5px; cursor: pointer; border: 1px solid #ff6b35; }
        
        .sidebar { position: fixed; top: 0; left: -80%; width: 80%; height: 100%; background: #111; transition: left 0.3s; z-index: 1000; padding: 20px; }
        .sidebar.open { left: 0; }
        .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); display: none; z-index: 999; }
        .overlay.show { display: block; }
        
        .profile-section { text-align: center; margin-bottom: 15px; }
        .profile-avatar { width: 60px; height: 60px; border-radius: 50%; background: #ff6b35; margin: 0 auto 5px; display: flex; align-items: center; justify-content: center; font-size: 30px; }
        .separator { border-bottom: 1px solid #333; margin: 15px 0; }
        
        .chat-item { background: #1a1a1a; padding: 12px; margin-bottom: 8px; border-radius: 8px; cursor: pointer; border: 1px solid #333; }
        .chat-item:hover { border-color: #ff6b35; }
    </style>
</head>
<body>
    <div class="overlay" id="overlay" onclick="toggleMenu()"></div>
    <div class="sidebar" id="sidebar">
        <div class="profile-section">
            <div class="profile-avatar">🤖</div>
            <h3>Джекс</h3>
            <p style="color: #888; font-size: 14px;">ИИ Ассистент v1.01</p>
        </div>
        
        <div class="separator"></div>
        
        <div class="chat-item" onclick="newChat()">➕ Новый чат</div>
        
        <div class="separator"></div>
        
        <div class="chat-item" onclick="loadChat(1)">💬 Чат 1</div>
        
        <div class="separator"></div>
        
        <div class="chat-item" onclick="alert('Настройки скоро!')">⚙️ Настройки</div>
    </div>
    
    <header>
        <button class="menu-btn" onclick="toggleMenu()">☰</button>
        <span style="font-weight: bold;">Джекс</span>
        <button class="new-chat-btn" onclick="newChat()">+</button>
    </header>
    
    <div id="chat">
        <div class="msg ai">Привет! Я Джекс. Чем помочь?</div>
    </div>
    
    <div class="input-area">
        <div class="preview" id="preview"></div>
        <div class="input-row">
            <input type="file" id="fileInput" accept="image/*" multiple style="display:none">
            <button class="photo-btn" onclick="document.getElementById('fileInput').click()">📷</button>
            <input type="text" id="input" placeholder="Сообщение..." maxlength="1000">
            <button class="send-btn" onclick="send()">➔</button>
        </div>
    </div>
    
    <script>
        let images = [];
        let touchStartX = 0;
        let touchStartY = 0;
        
        document.getElementById('fileInput').onchange = function(e) {
            for(let file of e.target.files) {
                if(images.length >= 10) { alert('Максимум 10 фото!'); break; }
                if(file.size > 10 * 1024 * 1024) { alert('Фото слишком большое!'); continue; }
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
                p.innerHTML += '<img src="' + img + '" onclick="removeImage(' + i + ')">';
            });
        }
        
        function removeImage(index) {
            images.splice(index, 1);
            updatePreview();
        }
        
        function toggleMenu() {
            document.getElementById('sidebar').classList.toggle('open');
            document.getElementById('overlay').classList.toggle('show');
        }
        
        function newChat() {
            document.getElementById('chat').innerHTML = '<div class="msg ai">Новый чат!</div>';
            toggleMenu();
        }
        
        function loadChat(id) {
            document.getElementById('chat').innerHTML = '<div class="msg ai">Чат ' + id + '</div>';
            toggleMenu();
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        async function send() {
            const input = document.getElementById('input');
            const chat = document.getElementById('chat');
            const text = input.value.trim();
            
            if(!text && images.length === 0) return;
            
            let html = '';
            if(images.length > 0) {
                images.forEach(img => { html += '<img src="' + img + '" style="width:40px;height:40px;border-radius:5px;margin:2px">'; });
            }
            
            chat.innerHTML += '<div class="msg user">' + html + escapeHtml(text) + '</div>';
            input.value = '';
            chat.scrollTop = chat.scrollHeight;
            
            const sentImages = [...images];
            images = [];
            updatePreview();
            
            try {
                const res = await fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: text, images: sentImages})
                });
                const data = await res.json();
                chat.innerHTML += '<div class="msg ai">' + escapeHtml(data.reply) + '</div>';
            } catch(e) {
                chat.innerHTML += '<div class="msg ai">Ошибка</div>';
            }
            
            chat.scrollTop = chat.scrollHeight;
        }
        
        document.addEventListener('touchstart', function(e) {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        });
        
        document.addEventListener('touchend', function(e) {
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            const diffX = touchEndX - touchStartX;
            const diffY = touchEndY - touchStartY;
            
            if(Math.abs(diffX) > Math.abs(diffY) && diffX > 80 && touchStartX < 50) {
                toggleMenu();
            }
        });
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
        
        # ИСПРАВЛЕНО: проверка типа images
        if not isinstance(images, list):
            images = []
        
        ai_reply = jax.generate_response(user_message, images)
        return jsonify({'reply': ai_reply})
    except Exception as e:
        logger.error(f"Ошибка в /ask: {e}")
        return jsonify({'reply': 'Внутренняя ошибка сервера'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)