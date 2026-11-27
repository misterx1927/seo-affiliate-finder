from pathlib import Path
from streamlit.testing.v1 import AppTest

app = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py")).run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
source = next(item for item in app.radio if item.label == "Источник данных")
source.set_value("Демо").run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
next(item for item in app.button if item.label == "Обновить демо").click().run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
metrics = {item.label: item.value for item in app.metric}
assert metrics == {"ЗАПРОСЫ": "10", "ПОЗИЦИИ": "30", "СТРАНИЦЫ": "3", "ВОЗМОЖНЫЕ ПЛОЩАДКИ": "1"}, metrics
assert app.selectbox[0].value == "Все запросы"
queue = next(item for item in app.multiselect if item.label == "Показать")
queue.set_value(["Возможные площадки"]).run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
assert len(app.dataframe[0].value) == 1
assert app.dataframe[0].value["№"].tolist() == [1]
assert "Позиция" in app.dataframe[0].value.columns
assert set(app.dataframe[0].value["Запросов в топ-10"]) == {10}
assert set(app.dataframe[0].value["Оценка"]) == {"Возможно подходит"}
assert len(app.dataframe[1].value) == 10
app.selectbox[0].select("online casino canada").run(timeout=30)
assert not app.exception
assert len(app.dataframe[0].value) == 1
app.selectbox[0].select("Все запросы").run(timeout=30)
next(item for item in app.multiselect if item.label == "Показать").set_value(["Нужна проверка", "Не подходят"]).run(timeout=30)
assert not app.exception
next(item for item in app.radio if item.label == "Источник данных").set_value("Сохранённый прогон").run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
metrics = {item.label: item.value for item in app.metric}
assert metrics["ЗАПРОСЫ"] == "10" and metrics["ПОЗИЦИИ"] == "100" and metrics["СТРАНИЦЫ"] == "69", metrics
assert not app.progress
assert not any("Дополнительная проверка: 27" in item.value for item in app.caption)
assert any("Google Web" in item.value for item in app.caption)
next(item for item in app.multiselect if item.label == "Показать").set_value(["Возможные площадки"]).run(timeout=30)
contacts = app.dataframe[0].value["Возможный контакт"].values
assert "marketing@casinoslists.com" in contacts
assert "marketing@slotsmate.com" in contacts
assert "ad.ops@livescore.com" in contacts
assert "info@cflnewshub.com" in contacts
assert "См. страницу контактов" in contacts
assert not any(value == "" for value in contacts)
saved_table = app.dataframe[0].value
domains = saved_table["Ссылка на страницу"].str.extract(r"^https?://(?:www\.)?([^/]+)", expand=False).str.lower()
assert not domains.duplicated().any(), domains.tolist()
assert len(saved_table) == int(metrics["ВОЗМОЖНЫЕ ПЛОЩАДКИ"])
for domain, contact_page in {
    "pokertube.com": "https://www.pokertube.com/contact",
    "squawka.com": "https://www.squawka.com/ca/help-and-faqs/",
    "sigma.world": "https://sigma.world/contact/",
}.items():
    matching = saved_table[saved_table["Ссылка на страницу"].str.contains(domain, regex=False)]
    assert len(matching) > 0, f"{domain}: missing from saved results"
    assert set(matching["Страница контактов"]) == {contact_page}, domain
    assert set(matching["Возможный контакт"]) == {"См. страницу контактов"}, domain
app.selectbox[0].select("fast payout casino canada").run(timeout=30)
next(item for item in app.selectbox if item.label == "Выберите площадку").select("casino.ca").run(timeout=30)
pages = next(item for item in app.selectbox if item.label == "Страница площадки").options
assert any("/fast-withdrawals/" in page for page in pages), pages
assert any("/highest-payouts/" in page for page in pages), pages
next(item for item in app.multiselect if item.label == "Показать").set_value([]).run(timeout=30)
assert app.dataframe and len(app.dataframe[0].value) > 0
app.selectbox[0].select("Все запросы").run(timeout=30)
next(item for item in app.multiselect if item.label == "Показать").set_value(
    ["Возможные площадки", "Нужна проверка", "Не подходят", "Нет анализа"]
).run(timeout=30)
assert not app.exception
if app.dataframe:
    positions = app.dataframe[0].value["Позиция"].tolist()
    assert positions == sorted(positions), positions
    urls = app.dataframe[0].value["Ссылка на страницу"].astype(str)
    assert not urls.str.contains(r"^https?://(?:[^/]+\.)?trustpilot\.com(?:/|$)", case=False, regex=True).any()
next(item for item in app.radio if item.label == "Источник данных").set_value("Реальные результаты").run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
assert not any("Обновить демо" in button.label for button in app.button)
assert not app.progress
if app.dataframe:
    table = app.dataframe[0].value
    missing_contact = table[table["Возможный контакт"].eq("Не найден")]
    assert not (missing_contact["Оценка"] == "Возможно подходит").any()
    next(item for item in app.multiselect if item.label == "Показать").set_value(["Нужна проверка"]).run(timeout=30)
    assert not app.exception, [item.value for item in app.exception]
    if app.dataframe:
        table = app.dataframe[0].value
        missing_contact = table[table["Возможный контакт"].eq("Не найден")]
        assert (missing_contact["Оценка"] == "Нужна проверка").all()
print("UI smoke test passed: Russian demo, filters, saved snapshot and live mode.")

