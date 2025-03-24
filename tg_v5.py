import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from fpdf import FPDF

# Состояния для ConversationHandler
(
    SELECTING_HOUSE,
    SELECTING_WORK_TYPE,
    RECEIVING_PHOTO_BEFORE,
    CHOOSING_ACTION,
    RECEIVING_TASK_NUMBER,
    RECEIVING_PHOTO_AFTER,
) = range(6)

# Список домов
HOUSES = ["10", "11", "12"]

# Кнопки
ACTION_KEYBOARD = [["Добавить фото выполненной работы", "Добавить фото позже"]]
CONTINUE_KEYBOARD = [["Продолжить не выполненную работу", "Начать новую"]]

# Путь к шрифту
FONT_PATH = "/Users/nikolajusakov/PycharmProjects/PythonProject/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf"

# Проверка наличия шрифта
if not os.path.exists(FONT_PATH):
    print(f"Шрифт {FONT_PATH} не найден. Убедитесь, что файл находится в указанной директории.")
    exit(1)


# Функция для создания структуры каталогов
def create_report_directory(house):
    now = datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    base_dir = os.path.join("reports", year, house, month)

    # Находим последний номер отчета
    report_number = 1
    while os.path.exists(os.path.join(base_dir, f"report_{report_number}")):
        report_number += 1

    report_dir = os.path.join(base_dir, f"report_{report_number}")
    os.makedirs(report_dir, exist_ok=True)
    print(f"Директория создана: {report_dir}")
    return report_dir


# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Переходим к выбору дома
    return await select_house(update, context)


# Обработчик выбора дома
async def select_house(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем незавершенные работы
    await check_unfinished(update, context)

    # Если есть незавершенные работы, бот остановится на CHOOSING_ACTION
    if context.user_data.get("unfinished_tasks"):
        return CHOOSING_ACTION

    # Если незавершенных работ нет, переходим к выбору дома
    keyboard = [[house] for house in HOUSES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Выберите номер дома:", reply_markup=reply_markup)
    return SELECTING_HOUSE


# Обработчик ввода типа работ
async def select_work_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    work_type = update.message.text
    context.user_data["work_type"] = work_type
    await update.message.reply_text("Пришлите фото до начала работ.")
    return RECEIVING_PHOTO_BEFORE


# Обработчик получения фото "до начала работ"
async def handle_photo_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    # Создаем папку для отчета и сохраняем путь в context.user_data
    if "report_dir" not in context.user_data:
        context.user_data["report_dir"] = create_report_directory(context.user_data["selected_house"])

    report_dir = context.user_data["report_dir"]
    photo_before_path = os.path.join(report_dir, "до.jpg")

    try:
        await file.download_to_drive(photo_before_path)
        print(f"Фото 'до начала работ' успешно сохранено: {photo_before_path}")
    except Exception as e:
        print(f"Ошибка при сохранении фото 'до начала работ': {e}")
        await update.message.reply_text("Ошибка при сохранении фото. Пожалуйста, попробуйте еще раз.")
        return RECEIVING_PHOTO_BEFORE

    context.user_data["photo_before"] = photo_before_path

    # Отправляем кнопки
    reply_markup = ReplyKeyboardMarkup(ACTION_KEYBOARD, one_time_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

    return CHOOSING_ACTION


# Обработчик выбора действия
async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_choice = update.message.text

    if user_choice == "Продолжить не выполненную работу":
        await update.message.reply_text("Введите номер не выполненной работы:")
        return RECEIVING_TASK_NUMBER
    elif user_choice == "Начать новую":
        return await start(update, context)


# Обработчик получения номера задачи
async def receive_task_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_number = int(update.message.text)
        unfinished_tasks = context.user_data.get("unfinished_tasks", [])

        if task_number < 1 or task_number > len(unfinished_tasks):
            await update.message.reply_text("Неверный номер задачи. Пожалуйста, введите корректный номер.")
            return RECEIVING_TASK_NUMBER

        # Получаем путь к папке выбранной задачи
        _, _, report_dir = unfinished_tasks[task_number - 1]
        context.user_data["current_report_dir"] = report_dir

        await update.message.reply_text("Пришлите фото выполненной работы.")
        return RECEIVING_PHOTO_AFTER
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число.")
        return RECEIVING_TASK_NUMBER


# Обработчик получения фото "после окончания работ"
async def handle_photo_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    report_dir = context.user_data.get("current_report_dir")
    if not report_dir:
        await update.message.reply_text("Ошибка: папка не найдена.")
        return ConversationHandler.END

    photo_after_path = os.path.join(report_dir, "после.jpg")

    try:
        await file.download_to_drive(photo_after_path)
        print(f"Фото 'после окончания работ' успешно сохранено: {photo_after_path}")
    except Exception as e:
        print(f"Ошибка при сохранении фото 'после окончания работ': {e}")
        await update.message.reply_text("Ошибка при сохранении фото. Пожалуйста, попробуйте еще раз.")
        return RECEIVING_PHOTO_AFTER

    # Обновляем текстовый документ
    text_file_path = os.path.join(report_dir, "report.txt")
    try:
        with open(text_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(text_file_path, "w", encoding="utf-8") as f:
            for line in lines:
                if "не выполнено" in line:
                    f.write("Статус: выполнено\n")
                else:
                    f.write(line)
        print(f"Текстовый файл обновлен: {text_file_path}")
    except Exception as e:
        print(f"Ошибка при обновлении текстового файла: {e}")

    # Извлекаем данные из файла report.txt
    house_number, work_type = extract_report_data(report_dir)
    if not house_number or not work_type:
        await update.message.reply_text("Ошибка: не удалось извлечь данные из отчета.")
        return ConversationHandler.END

    # Создаем PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
    pdf.set_font("DejaVu", size=12)

    # Добавляем текст в PDF
    pdf.cell(200, 10, txt=f"Номер дома: {house_number}", ln=True)
    pdf.cell(200, 10, txt=f"Тип работ: {work_type}", ln=True)
    pdf.cell(200, 10, txt="Статус: выполнено", ln=True)

    # Добавляем фото в PDF
    pdf.image(os.path.join(report_dir, "до.jpg"), x=10, y=50, w=90)
    pdf.image(photo_after_path, x=110, y=50, w=90)

    pdf_output = os.path.join(report_dir, "report.pdf")
    try:
        pdf.output(pdf_output)
        print(f"PDF успешно создан: {pdf_output}")
    except Exception as e:
        print(f"Ошибка при создании PDF: {e}")
        await update.message.reply_text("Ошибка при создании PDF. Пожалуйста, попробуйте еще раз.")
        return ConversationHandler.END

    # Отправляем PDF пользователю
    try:
        with open(pdf_output, "rb") as file:
            await update.message.reply_document(document=file, caption=f"Отчет для дома №{house_number}")
    except Exception as e:
        print(f"Ошибка при отправке PDF: {e}")
        await update.message.reply_text("Ошибка при отправке PDF.")

    # Создаем новую папку для следующих файлов
    context.user_data["report_dir"] = create_report_directory(house_number)
    await update.message.reply_text("Папка заполнена. Начните новую задачу. Введите номер дома.")
    return SELECTING_HOUSE


# Извлечение данных из файла report.txt
def extract_report_data(report_dir):
    text_file_path = os.path.join(report_dir, "report.txt")
    try:
        with open(text_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            house_number = lines[0].split(": ")[1].strip()
            work_type = lines[1].split(": ")[1].strip()
            return house_number, work_type
    except Exception as e:
        print(f"Ошибка при чтении файла report.txt: {e}")
        return None, None

# Команда для проверки незавершенных работ
async def check_unfinished(update: Update, context: ContextTypes.DEFAULT_TYPE):
    base_dir = "reports"
    unfinished_tasks = []

    # Рекурсивно ищем все текстовые файлы
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file == "report.txt":
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "не выполнено" in content:
                        # Извлекаем номер дома и тип работ
                        lines = content.split("\n")
                        house_number = lines[0].split(": ")[1]
                        work_type = lines[1].split(": ")[1]
                        unfinished_tasks.append((house_number, work_type, root))

    if not unfinished_tasks:
        await update.message.reply_text("Нет незавершенных работ.")
        return SELECTING_HOUSE  # Переходим к выбору дома

    # Формируем нумерованный список
    response = "Незавершенные работы:\n"
    for i, (house_number, work_type, _) in enumerate(unfinished_tasks, start=1):
        response += f"{i}. Дом №{house_number}, Тип работ: {work_type}\n"

    await update.message.reply_text(response)

    # Отправляем кнопки
    reply_markup = ReplyKeyboardMarkup(CONTINUE_KEYBOARD, one_time_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

    # Сохраняем список незавершенных задач в context.user_data
    context.user_data["unfinished_tasks"] = unfinished_tasks

    return CHOOSING_ACTION


# Основная функция
def main():
    application = ApplicationBuilder().token('8127498518:AAFzskJYwY0-gkF2FdjJbtY1YcjZVd88wGs').build()  # Замените на ваш токен

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_HOUSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_house)],
            SELECTING_WORK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_work_type)],
            RECEIVING_PHOTO_BEFORE: [MessageHandler(filters.PHOTO, handle_photo_before)],
            CHOOSING_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            RECEIVING_TASK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_task_number)],
            RECEIVING_PHOTO_AFTER: [MessageHandler(filters.PHOTO, handle_photo_after)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("check_unfinished", check_unfinished))  # Добавляем команду
    application.run_polling()


if __name__ == '__main__':
    main()