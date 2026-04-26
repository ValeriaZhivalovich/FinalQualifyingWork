import json
import os
from datetime import datetime
from typing import Dict, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)

class FeedbackManager:
    """Менеджер для сохранения обратной связи пользователей"""
    
    def __init__(self, max_items: int = 100):
        self.max_items = max_items
        self.feedback_file = "data/feedback.json"
        self.export_file = "data/feedback_export.txt"
        self.feedback_data = self._load_feedback()
        
    def _load_feedback(self) -> Dict:
        """Загружает данные фидбека из файла"""
        os.makedirs("data", exist_ok=True)
        
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Конвертируем списки обратно в deque с ограничением
                    return {
                        'positive': deque(data.get('positive', []), maxlen=self.max_items),
                        'negative': deque(data.get('negative', []), maxlen=self.max_items),
                        'stats': data.get('stats', {
                            'total_likes': 0,
                            'total_dislikes': 0
                        })
                    }
            except Exception as e:
                logger.error(f"Ошибка загрузки feedback.json: {e}")
        
        return {
            'positive': deque(maxlen=self.max_items),
            'negative': deque(maxlen=self.max_items),
            'stats': {
                'total_likes': 0,
                'total_dislikes': 0
            }
        }
    
    def _save_feedback(self):
        """Сохраняет данные фидбека в файл"""
        try:
            # Конвертируем deque в списки для сериализации
            data_to_save = {
                'positive': list(self.feedback_data['positive']),
                'negative': list(self.feedback_data['negative']),
                'stats': self.feedback_data['stats']
            }
            
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
                
            # Автоматически экспортируем в текстовый файл
            self.export_to_text()
                
        except Exception as e:
            logger.error(f"Ошибка сохранения feedback.json: {e}")
    
    def add_feedback(self, 
                    message_id: int,
                    chat_id: int,
                    question: str,
                    answer: str,
                    is_positive: bool,
                    user_id: Optional[int] = None,
                    context: Optional[str] = None) -> Dict:
        """
        Добавляет фидбек для ответа
        
        Returns:
            Dict с информацией о результате
        """
        feedback_item = {
            'message_id': message_id,
            'chat_id': chat_id,
            'question': question[:500],  # Увеличил лимит
            'answer': answer[:1000],  # Увеличил лимит
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'context': context[:2000] if context else None
        }
        
        if is_positive:
            self.feedback_data['positive'].append(feedback_item)
            self.feedback_data['stats']['total_likes'] += 1
            result = {
                'status': 'success',
                'type': 'positive',
                'message': '🔥 Отличный ответ записан!'
            }
            logger.info(f"[{chat_id}] 🔥 Положительный фидбек для сообщения {message_id}")
        else:
            self.feedback_data['negative'].append(feedback_item)
            self.feedback_data['stats']['total_dislikes'] += 1
            result = {
                'status': 'success', 
                'type': 'negative',
                'message': '🤨 Сомнительный ответ записан для анализа'
            }
            logger.info(f"[{chat_id}] 🤨 Отрицательный фидбек для сообщения {message_id}")
        
        # Сохраняем
        self._save_feedback()
        
        return result
    
    def export_to_text(self):
        """Экспортирует фидбек в текстовый файл для ручного анализа"""
        try:
            with open(self.export_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("ЭКСПОРТ ФИДБЕКА ДЛЯ РУЧНОГО АНАЛИЗА\n")
                f.write(f"Дата экспорта: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Всего оценок: 🔥 {self.feedback_data['stats']['total_likes']} | 🤨 {self.feedback_data['stats']['total_dislikes']}\n")
                f.write("=" * 80 + "\n\n")
                
                # Экспортируем положительные примеры
                f.write("🔥 ХОРОШИЕ ОТВЕТЫ (можно использовать как примеры):\n")
                f.write("-" * 40 + "\n\n")
                
                for i, item in enumerate(list(self.feedback_data['positive']), 1):
                    f.write(f"Пример #{i} [{item['timestamp']}]\n")
                    f.write(f"Вопрос: {item['question']}\n")
                    f.write(f"Ответ: {item['answer']}\n")
                    if item.get('context'):
                        f.write(f"Контекст: {item['context'][:500]}...\n")
                    f.write("\n")
                
                # Экспортируем отрицательные примеры
                f.write("\n" + "=" * 80 + "\n")
                f.write("🤨 ПЛОХИЕ ОТВЕТЫ (нужно избегать таких):\n")
                f.write("-" * 40 + "\n\n")
                
                for i, item in enumerate(list(self.feedback_data['negative']), 1):
                    f.write(f"Пример #{i} [{item['timestamp']}]\n")
                    f.write(f"Вопрос: {item['question']}\n")
                    f.write(f"Ответ: {item['answer']}\n")
                    if item.get('context'):
                        f.write(f"Контекст: {item['context'][:500]}...\n")
                    f.write("\n")
                
                logger.info(f"Фидбек экспортирован в {self.export_file}")
                
        except Exception as e:
            logger.error(f"Ошибка экспорта фидбека: {e}")
    
    def get_stats(self) -> Dict:
        """Возвращает статистику фидбека"""
        total = self.feedback_data['stats']['total_likes'] + self.feedback_data['stats']['total_dislikes']
        
        return {
            'total_feedback': total,
            'likes': self.feedback_data['stats']['total_likes'],
            'dislikes': self.feedback_data['stats']['total_dislikes'],
            'like_rate': self.feedback_data['stats']['total_likes'] / total if total > 0 else 0,
            'recent_positive': len(self.feedback_data['positive']),
            'recent_negative': len(self.feedback_data['negative'])
        }

# Создаем глобальный экземпляр
feedback_manager = FeedbackManager()