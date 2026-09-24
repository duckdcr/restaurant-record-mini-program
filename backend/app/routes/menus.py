from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User
from ..services.menus import copy_previous_menu, get_menu_for_date, save_menu, serialize_menu


router = APIRouter(prefix="/menus", tags=["menus"])
Meal = Literal["breakfast", "lunch", "dinner", "snack"]


class MenuWrite(BaseModel):
    items: list[str] = Field(max_length=100)


@router.get("/{menu_date}")
def get_menu(menu_date: date, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return get_menu_for_date(db, menu_date)


@router.put("/{menu_date}/{meal}")
def put_menu(
    menu_date: date,
    meal: Meal,
    payload: MenuWrite,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return serialize_menu(save_menu(db, menu_date, meal, payload.items, user))


@router.post("/{menu_date}/copy-previous")
def copy_menu(menu_date: date, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return copy_previous_menu(db, menu_date, user)

