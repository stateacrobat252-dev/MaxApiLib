import pytest
from src.maxbot_easy.types import Button

def test_button_init():
    btn = Button('Test', payload='p1')
    assert btn.text == 'Test'
    assert btn.payload == 'p1'

def test_button_callback():
    btn = Button.callback('Click', 'payload')
    assert btn.text == 'Click'
    assert btn.payload == 'payload'

def test_button_link():
    btn = Button.link('Link', 'https://google.com')
    assert btn.text == 'Link'
    assert btn.url == 'https://google.com'

def test_button_link_invalid():
    with pytest.raises(ValueError, match='Ссылка должна начинаться с http:// или https://'):
        Button.link('Link', 'invalid_url')

def test_button_contact():
    btn = Button.contact()
    assert btn.text == 'Отправить контакт'

def test_button_location():
    btn = Button.location()
    assert btn.text == 'Отправить геолокацию'

def test_button_chat():
    btn = Button.chat('Chat', 'Title', 'Desc')
    assert btn.text == 'Chat'
    assert btn.title == 'Title'
    assert btn.description == 'Desc'

def test_button_to_dict():
    btn = Button.callback('Btn', 'Pay')
    d = btn.to_dict()
    assert d == {'text': 'Btn', 'payload': 'Pay', 'url': None, 'title': None, 'description': None}
