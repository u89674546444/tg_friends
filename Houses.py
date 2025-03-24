import pandas as pd
import json

# Путь к файлу
file_path = '/Users/nikolajusakov/PycharmProjects/PythonProject/список дом.xls'

try:
    # Чтение данных из Excel-файла
    data = pd.read_excel(file_path, skiprows=12, sheet_name='Лист_1', engine='xlrd')

    # Создание словаря с возможностью повторяющихся ключей
    house_dict = {}

    # Перебор строк в данных
    for index, row in data.iterrows():
        # Предполагаем, что адрес находится в первом столбце (индекс 0)
        address = row.iloc[0]  # Используем iloc для доступа по позиции

        # Извлечение номера дома из адреса
        # Пример: "Уфа, Бехтерева,д. 16" -> номер дома "16"
        if isinstance(address, str) and "д." in address:
            house_number = address.split("д.")[-1].strip()  # Извлекаем номер дома

            # Если номер дома уже есть в словаре, добавляем адрес в список
            if house_number in house_dict:
                house_dict[house_number].append(address)
            else:
                # Иначе создаем новый список с адресом
                house_dict[house_number] = [address]

    # Сохранение словаря в JSON-файл
    output_file = '/Users/nikolajusakov/PycharmProjects/PythonProject/dic_houses.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(house_dict, f, ensure_ascii=False, indent=4)

    print(f"Словарь успешно сохранен в файл: {output_file}")

except Exception as e:
    print(f"Произошла ошибка: {e}")