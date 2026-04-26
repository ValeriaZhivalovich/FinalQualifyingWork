from typing import List
from .base import BaseCollector
from ..models import RawArticle


class VKCollector(BaseCollector):
    source_name = "vk"

    def fetch(self) -> List[RawArticle]:
        # TODO: Implement VK fetching using vk_api
        return []

    def validate_config(self) -> bool:
        # TODO: Validate VK API config
        return True