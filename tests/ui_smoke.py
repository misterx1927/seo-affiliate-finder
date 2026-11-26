from pathlib import Path
from streamlit.testing.v1 import AppTest

app = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py")).run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
source = next(item for item in app.radio if item.label == "Источник данных")
source.set_value("Демо").run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
app.text_input[0].input("casino").run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
app.text_input[0].input("").run(timeout=30)
next(item for item in app.button if item.label == "Обновить демо").click().run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
metrics = {item.label: item.value for item in app.metric}
assert metrics == {"ЗАПРОСЫ": "10", "ПОЗИЦИИ": "30", "СТРАНИЦЫ": "3", "ВОЗМОЖНЫЕ ПЛОЩАДКИ": "1"}, metrics
assert app.selectbox[0].value == "Все запросы"
queue = next(item for item in app.multiselect if item.label == "Показать")
queue.set_value(["Возможные площадки"]).run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
assert len(app.dataframe[0].value) == 10
assert app.dataframe[0].value["№"].tolist() == list(range(1, 11))
assert "Позиция" in app.dataframe[0].value.columns
assert set(app.dataframe[0].value["Запросов в топ-10"]) == {10}
assert set(app.dataframe[0].value["Оценка"]) == {"Возможно подходит"}
app.text_input[0].input("reviews.example").run(timeout=30)
assert not app.exception
assert len(app.dataframe[0].value) == 10
app.selectbox[0].select("online casino canada").run(timeout=30)
assert not app.exception
assert len(app.dataframe[0].value) == 1
app.selectbox[0].select("Все запросы").run(timeout=30)
app.text_input[0].input("").run(timeout=30)
next(item for item in app.multiselect if item.label == "Показать").set_value(["Нужна проверка", "Не подходят"]).run(timeout=30)
assert not app.exception
next(item for item in app.radio if item.label == "Источник данных").set_value("Сохранённый прогон").run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
metrics = {item.label: item.value for item in app.metric}
assert metrics["ЗАПРОСЫ"] == "10" and metrics["ПОЗИЦИИ"] == "100" and metrics["СТРАНИЦЫ"] == "69", metrics
assert any("Google Web" in item.value for item in app.caption)
next(item for item in app.multiselect if item.label == "Показать").set_value(["Возможные площадки"]).run(timeout=30)
app.text_input[0].input("casinoslists.com").run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
assert "marketing@casinoslists.com" in app.dataframe[0].value["Возможный контакт"].values
app.text_input[0].input("").run(timeout=30)
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
assert len(app.progress) == 1
print("UI smoke test passed: Russian demo, filters, saved snapshot and live mode.")

