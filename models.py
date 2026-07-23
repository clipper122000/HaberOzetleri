from pydantic import BaseModel
from typing import Optional

class NewsItem(BaseModel):
    title: str
    link: str
    source: str
    description: Optional[str] = ""
    pub_date: Optional[str] = ""
    iso_date: Optional[str] = None  # ISO format UTC timestamp for filtering/sorting
    type: Optional[str] = "local"  # "local" or "global"
