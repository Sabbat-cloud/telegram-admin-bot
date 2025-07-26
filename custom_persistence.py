# custom_persistence.py
import json
import logging
from collections import defaultdict
from copy import deepcopy
from typing import Any, DefaultDict, Dict, Optional, Tuple

from telegram.ext import BasePersistence

# Configura un logger específico para esta clase
logger = logging.getLogger(__name__)
class JsonPersistence(BasePersistence):
    def __init__(self, filepath: str):
        # Versión compatible que no pasa los argumentos de store_*
        super().__init__()
        self.filepath = filepath
        self.user_data: Optional[DefaultDict[int, Dict]] = None
        self.chat_data: Optional[DefaultDict[int, Dict]] = None
        self.bot_data: Optional[Dict] = None
        self.callback_data: Optional[Dict] = None
        self.on_flush = False

    def _load_data(self) -> Tuple[DefaultDict[int, Dict], DefaultDict[int, Dict], Dict, Dict]:
        """Carga los datos desde el fichero JSON."""
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
                user_data = defaultdict(dict, {int(k): v for k, v in data.get("user_data", {}).items()})
                chat_data = defaultdict(dict, {int(k): v for k, v in data.get("chat_data", {}).items()})
                bot_data = data.get("bot_data", {})
                callback_data = data.get("callback_data", {})
                return user_data, chat_data, bot_data, callback_data
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning(f"No se pudo cargar el fichero de persistencia o está vacío: {self.filepath}")
            return defaultdict(dict), defaultdict(dict), {}, {}

    def _save_data(self) -> None:
        """Guarda los datos en el fichero JSON."""
        if self.on_flush:
            return

        self.on_flush = True
        try:
            data_to_save = {
                "user_data": deepcopy(self.user_data),
                "chat_data": deepcopy(self.chat_data),
                "bot_data": deepcopy(self.bot_data),
                "callback_data": deepcopy(self.callback_data),
            }
            with open(self.filepath, "w") as f:
                json.dump(data_to_save, f, indent=2)
        except Exception as e:
            logger.error(f"Error al guardar los datos de persistencia: {e}", exc_info=True)
        finally:
            self.on_flush = False

    async def get_bot_data(self) -> Dict[Any, Any]:
        """Devuelve los datos del bot."""
        if self.bot_data is None:
            self.user_data, self.chat_data, self.bot_data, self.callback_data = self._load_data()
        return deepcopy(self.bot_data)

    async def get_chat_data(self) -> DefaultDict[int, Dict[Any, Any]]:
        """Devuelve los datos del chat."""
        if self.chat_data is None:
            self.user_data, self.chat_data, self.bot_data, self.callback_data = self._load_data()
        return deepcopy(self.chat_data)

    async def get_user_data(self) -> DefaultDict[int, Dict[Any, Any]]:
        """Devuelve los datos del usuario."""
        if self.user_data is None:
            self.user_data, self.chat_data, self.bot_data, self.callback_data = self._load_data()
        return deepcopy(self.user_data)

    async def get_callback_data(self) -> Optional[Dict]:
        """Devuelve los datos de callback."""
        if self.callback_data is None:
            self.user_data, self.chat_data, self.bot_data, self.callback_data = self._load_data()
        return deepcopy(self.callback_data)

    async def update_bot_data(self, data: Dict) -> None:
        """Actualiza los datos del bot en memoria."""
        if self.bot_data is None:
            self.bot_data = {}
        self.bot_data.update(deepcopy(data))

    async def update_chat_data(self, chat_id: int, data: Dict) -> None:
        """Actualiza los datos de un chat en memoria."""
        if self.chat_data is None:
            self.chat_data = defaultdict(dict)
        self.chat_data[chat_id].update(deepcopy(data))

    async def update_user_data(self, user_id: int, data: Dict) -> None:
        """Actualiza los datos de un usuario en memoria."""
        if self.user_data is None:
            self.user_data = defaultdict(dict)
        self.user_data[user_id].update(deepcopy(data))

    async def update_callback_data(self, data: Dict) -> None:
        """Actualiza los datos de callback en memoria."""
        self.callback_data = deepcopy(data)

    async def drop_chat_data(self, chat_id: int) -> None:
        """Elimina los datos de un chat."""
        if self.chat_data is not None and chat_id in self.chat_data:
            del self.chat_data[chat_id]

    async def drop_user_data(self, user_id: int) -> None:
        """Elimina los datos de un usuario."""
        if self.user_data is not None and user_id in self.user_data:
            del self.user_data[user_id]

    async def flush(self) -> None:
        """Guarda todos los datos de memoria al fichero JSON."""
        self._save_data()

    async def refresh_bot_data(self, bot_data: Dict) -> None:
        """Refresca los datos del bot desde la aplicación."""
        self.bot_data = bot_data

    async def refresh_chat_data(self, chat_id: int, chat_data: Dict) -> None:
        """Refresca los datos de un chat desde la aplicación."""
        self.chat_data[chat_id] = chat_data

    async def refresh_user_data(self, user_id: int, user_data: Dict) -> None:
        """Refresca los datos de un usuario desde la aplicación."""
        self.user_data[user_id] = user_data

    async def get_conversations(self, name: str) -> Dict:
        """Obtiene una conversación."""
        if self.bot_data is None:
            await self.get_bot_data()
        return self.bot_data.get("conversations", {}).get(name, {})

    async def update_conversation(
        self, name: str, key: Tuple[int, ...], new_state: Optional[object]
    ) -> None:
        """Actualiza una conversación."""
        if "conversations" not in self.bot_data:
            self.bot_data["conversations"] = {}
        if name not in self.bot_data["conversations"]:
            self.bot_data["conversations"][name] = {}
        
        str_key = ",".join(map(str, key))

        if new_state is not None:
            self.bot_data["conversations"][name][str_key] = new_state
        elif str_key in self.bot_data["conversations"][name]:
            del self.bot_data["conversations"][name][str_key]
