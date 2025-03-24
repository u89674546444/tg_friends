import pandas as pd
import json

# Укажите правильный путь к файлу
file_path = '/Users/nikolajusakov/PycharmProjects/PythonProject/Список работ.xlsx'  # Замените на ваш путь

# Чтение данных из Excel с указанием движка
try:
    df = pd.read_excel(file_path, sheet_name='Лист_1', engine='openpyxl')
except ValueError as e:
    print(f"Ошибка при чтении файла: {e}")
    exit(1)

# Создание списка для хранения отфильтрованных данных
filtered_data = []
seen_names = set()  # Множество для отслеживания уже добавленных наименований

# Перебор всех строк в DataFrame
for index, row in df.iterrows():
    # Проверка, что первый столбец не пустой
    if pd.notna(row.iloc[0]):
        # Убираем слова до точки и саму точку
        name = row.iloc[0].split('.')[-1].strip()  # Разделяем по точке и берем последнюю часть
        # Проверка, что строка не содержит "Материалы." или "Работа/услуги."
        if "Материалы." not in name and "Работа/услуги." not in name:
            # Проверка, что наименование еще не было добавлено
            if name not in seen_names:
                seen_names.add(name)  # Добавляем наименование в множество
                # Создание словаря для текущей строки
                item = {
                    "Наименование": name,  # Первый столбец без слов до точки
                    "Данные": " ".join(str(cell) for cell in row.iloc[1:] if pd.notna(cell))  # Объединение столбцов 2, 3, 4
                }
                filtered_data.append(item)

# Сохранение данных в JSON
with open('list_works.json', 'w', encoding='utf-8') as json_file:
    json.dump(filtered_data, json_file, ensure_ascii=False, indent=4)

print("Данные успешно сохранены в list_works.json")