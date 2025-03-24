import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from fpdf import FPDF

# Состояния для ConversationHandler
SELECTING_HOUSE, SELECTING_WORK_TYPE, RECEIVING_PHOTO_BEFORE, CHOOSING_ACTION, RECEIVING_PHOTO_AFTER = range(5)

# Список домов
HOUSES = ["10", "11", "12"]

# Кнопки
ACTION_KEYBOARD = [["Добавить фото выполненной работы", "Добавить фото позже"]]

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
    keyboard = [[house] for house in HOUSES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Выберите номер дома:", reply_markup=reply_markup)

    # Выполняем проверку незавершенных работ
    await check_unfinished(update, context)

    return SELECTING_HOUSE


# Обработчик выбора дома
async def select_house(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_house = update.message.text
    if selected_house not in HOUSES:
        await update.message.reply_text("Пожалуйста, выберите номер дома из списка.")
        return SELECTING_HOUSE

    context.user_data["selected_house"] = selected_house
    await update.message.reply_text("Введите тип работ:")
    return SELECTING_WORK_TYPE


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

    if user_choice == "Добавить фото выполненной работы":
        await update.message.reply_text("Пришлите фото выполненной работы.")
        return RECEIVING_PHOTO_AFTER
    elif user_choice == "Добавить фото позже":
        # Создаем текстовый документ с пометкой "не выполнено"
        report_dir = context.user_data["report_dir"]
        text_file_path = os.path.join(report_dir, "report.txt")
        try:
            with open(text_file_path, "w", encoding="utf-8") as text_file:
                text_file.write(f"Номер дома: {context.user_data['selected_house']}\n")
                text_file.write(f"Тип работ: {context.user_data['work_type']}\n")
                text_file.write("Статус: не выполнено\n")
            print(f"Текстовый файл успешно сохранен: {text_file_path}")
        except Exception as e:
            print(f"Ошибка при сохранении текстового файла: {e}")

        # Создаем PDF только с photo_before.jpg
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
        pdf.set_font("DejaVu", size=12)

        # Добавляем текст в PDF
        pdf.cell(200, 10, txt=f"Номер дома: {context.user_data['selected_house']}", ln=True)
        pdf.cell(200, 10, txt=f"Тип работ: {context.user_data['work_type']}", ln=True)
        pdf.cell(200, 10, txt="Статус: не выполнено", ln=True)

        # Добавляем фото в PDF
        pdf.image(context.user_data["photo_before"], x=10, y=50, w=90)

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
                await update.message.reply_document(document=file, caption=f"Отчет для дома №{context.user_data['selected_house']}")
        except Exception as e:
            print(f"Ошибка при отправке PDF: {e}")
            await update.message.reply_text("Ошибка при отправке PDF.")

        # Создаем новую папку для следующих файлов
        context.user_data["report_dir"] = create_report_directory(context.user_data["selected_house"])
        await update.message.reply_text("Папка заполнена. Начните новую задачу.")
        return SELECTING_HOUSE


# Обработчик получения фото "после окончания работ"
async def handle_photo_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    report_dir = context.user_data["report_dir"]
    photo_after_path = os.path.join(report_dir, "после.jpg")

    try:
        await file.download_to_drive(photo_after_path)
        print(f"Фото 'после окончания работ' успешно сохранено: {photo_after_path}")
    except Exception as e:
        print(f"Ошибка при сохранении фото 'после окончания работ': {e}")
        await update.message.reply_text("Ошибка при сохранении фото. Пожалуйста, попробуйте еще раз.")
        return RECEIVING_PHOTO_AFTER

    context.user_data["photo_after"] = photo_after_path

    # Создаем текстовый документ
    text_file_path = os.path.join(report_dir, "report.txt")
    try:
        with open(text_file_path, "w", encoding="utf-8") as text_file:
            text_file.write(f"Номер дома: {context.user_data['selected_house']}\n")
            text_file.write(f"Тип работ: {context.user_data['work_type']}\n")
            text_file.write("Статус: выполнено\n")
        print(f"Текстовый файл успешно сохранен: {text_file_path}")
    except Exception as e:
        print(f"Ошибка при сохранении текстового файла: {e}")

    # Создаем PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
    pdf.set_font("DejaVu", size=12)

    # Добавляем текст в PDF
    pdf.cell(200, 10, txt=f"Номер дома: {context.user_data['selected_house']}", ln=True)
    pdf.cell(200, 10, txt=f"Тип работ: {context.user_data['work_type']}", ln=True)
    pdf.cell(200, 10, txt="Статус: выполнено", ln=True)

    # Добавляем фото в PDF
    pdf.image(context.user_data["photo_before"], x=10, y=50, w=90)
    pdf.image(context.user_data["photo_after"], x=110, y=50, w=90)

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
            await update.message.reply_document(document=file, caption=f"Отчет для дома №{context.user_data['selected_house']}")
    except Exception as e:
        print(f"Ошибка при отправке PDF: {e}")
        await update.message.reply_text("Ошибка при отправке PDF.")

    # Создаем новую папку для следующих файлов
    context.user_data["report_dir"] = create_report_directory(context.user_data["selected_house"])
    await update.message.reply_text("Папка заполнена. Начните новую задачу.")
    return SELECTING_HOUSE


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
        await update.message.reply_text("Незавершенных работ не найдено.")
        return

    # Формируем нумерованный список
    response = "Незавершенные работы:\n"
    for i, (house_number, work_type, _) in enumerate(unfinished_tasks, start=1):
        response += f"{i}. Дом №{house_number}, Тип работ: {work_type}\n"

    await update.message.reply_text(response)


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
            RECEIVING_PHOTO_AFTER: [MessageHandler(filters.PHOTO, handle_photo_after)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("check_unfinished", check_unfinished))  # Добавляем команду
    application.run_polling()


if __name__ == '__main__':
    main()