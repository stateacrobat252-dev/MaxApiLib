import pytest
from src.maxbot_easy.types import Button, TextBox

def test_textbox_init():
    tb = TextBox("Привет")
    assert tb.text == "Привет"

def test_textbox_row():
    tb = TextBox("Меню")
    btn1 = Button.callback("A", "a")
    btn2 = Button.callback("B", "b")
    tb.row(btn1, btn2)
    assert len(tb.rows) == 1
    assert len(tb.rows[0]) == 2

def test_textbox_add():
    tb = TextBox("Текст")
    btn = Button.callback("Btn", "p")
    tb.add(btn)
    assert len(tb.rows) == 1
    assert tb.rows[0][0] == btn

def test_textbox_button():
    tb = TextBox("Меню")
    tb.button("Кнопка", "payload")
    assert len(tb.rows) == 1
    assert tb.rows[0][0].text == "Кнопка"
    assert tb.rows[0][0].payload == "payload"

def test_textbox_to_attachments():
    tb = TextBox("Текст")
    assert tb.to_attachments() is None

