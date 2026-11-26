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
assert app.selectbox[0].value == "online casino canada"
app.selectbox[0].select("Все запросы").run(timeout=30)
queue = next(item for item in app.multiselect if item.label == "Показать")
queue.set_value(["Возможные площадки"]).run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
assert len(app.dataframe[0].value) == 10
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
next(item for item in app.radio if item.label == "Источник данных").set_value("Реальные результаты").run(timeout=30)
assert not app.exception, [item.value for item in app.exception]
assert not any("Обновить демо" in button.label for button in app.button)
assert len(app.progress) == 1
assert any("Google Web" in item.value for item in app.caption)
print("UI smoke test passed: Russian demo, filters and live results.")

