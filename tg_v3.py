import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from fpdf import FPDF

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
SELECTING_HOUSE, SELECTING_WORK_TYPE, RECEIVING_PHOTO_BEFORE, RECEIVING_PHOTO_AFTER = range(4)

# Список домов
HOUSES = ["10", "11", "12"]

# Глобальные переменные для хранения данных
selected_house = None
work_type = None
photo_before = None
photo_after = None
photo_before_time = None
photo_after_time = None

# Путь к шрифту
FONT_PATH = "/Users/nikolajusakov/PycharmProjects/PythonProject/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf"

# Проверка наличия шрифта
if not os.path.exists(FONT_PATH):
    logger.error(f"Шрифт {FONT_PATH} не найден. Убедитесь, что файл находится в указанной директории.")
    exit(1)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Пользователь начал взаимодействие с ботом.")
    keyboard = [[house] for house in HOUSES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Выберите номер дома:", reply_markup=reply_markup)
    return SELECTING_HOUSE

# Обработчик выбора дома
async def select_house(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_house
    selected_house = update.message.text
    if selected_house not in HOUSES:
        await update.message.reply_text("Пожалуйста, выберите номер дома из списка.")
        return SELECTING_HOUSE
    logger.info(f"Выбран дом №{selected_house}.")
    await update.message.reply_text("Введите тип работ:")
    return SELECTING_WORK_TYPE

# Обработчик ввода типа работ
async def select_work_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global work_type
    work_type = update.message.text
    logger.info(f"Выбран тип работ: {work_type}.")
    await update.message.reply_text("Пришлите фото до начала работ.")
    return RECEIVING_PHOTO_BEFORE

# Обработчик получения фото "до начала работ"
async def handle_photo_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global photo_before, photo_before_time
    photo = update.message.photo[-1]
    file = await photo.get_file()
    photo_before = f"photo_before_{selected_house}.jpg"
    await file.download_to_drive(photo_before)
    photo_before_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Фото 'до начала работ' сохранено: {photo_before}.")
    await update.message.reply_text("Фото 'до начала работ' получено. Пришлите фото после окончания работ.")
    return RECEIVING_PHOTO_AFTER

# Обработчик получения фото "после окончания работ"
async def handle_photo_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global photo_after, photo_after_time
    photo = update.message.photo[-1]
    file = await photo.get_file()
    photo_after = f"photo_after_{selected_house}.jpg"
    await file.download_to_drive(photo_after)
    photo_after_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Фото 'после окончания работ' сохранено: {photo_after}.")

    # Создаем PDF
    pdf = FPDF()
    pdf.add_page()

    # Добавляем шрифт, поддерживающий UTF-8
    try:
        pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
        pdf.set_font("DejaVu", size=12)
    except RuntimeError as e:
        logger.error(f"Ошибка при загрузке шрифта: {e}")
        await update.message.reply_text("Ошибка при создании PDF: шрифт не найден.")
        return ConversationHandler.END

    # Добавляем текст в PDF
    pdf.cell(200, 10, txt=f"Номер дома: {selected_house}", ln=True)
    pdf.cell(200, 10, txt=f"Тип работ: {work_type}", ln=True)
    pdf.cell(200, 10, txt=f"Фото 'до начала работ' отправлено: {photo_before_time}", ln=True)
    pdf.cell(200, 10, txt=f"Фото 'после окончания работ' отправлено: {photo_after_time}", ln=True)

    # Добавляем фото в PDF
    pdf.image(photo_before, x=10, y=50, w=90)
    pdf.image(photo_after, x=110, y=50, w=90)

    pdf_output = f"report_{selected_house}.pdf"
    pdf.output(pdf_output)
    logger.info(f"PDF создан: {pdf_output}.")

    # Отправляем PDF пользователю
    try:
        with open(pdf_output, "rb") as file:
            await update.message.reply_document(document=file, caption=f"Отчет для дома №{selected_house}")
    except Exception as e:
        logger.error(f"Ошибка при отправке PDF: {e}")
        await update.message.reply_text("Ошибка при отправке PDF.")
    finally:
        # Очистка временных файлов
        if os.path.exists(photo_before):
            os.remove(photo_before)
        if os.path.exists(photo_after):
            os.remove(photo_after)
        if os.path.exists(pdf_output):
            os.remove(pdf_output)
        logger.info("Временные файлы удалены.")

    return ConversationHandler.END

# Обработчик отмены
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Пользователь отменил действие.")
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

# Основная функция
def main():
    application = ApplicationBuilder().token('8127498518:AAFzskJYwY0-gkF2FdjJbtY1YcjZVd88wGs').build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_HOUSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_house)],
            SELECTING_WORK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_work_type)],
            RECEIVING_PHOTO_BEFORE: [MessageHandler(filters.PHOTO, handle_photo_before)],
            RECEIVING_PHOTO_AFTER: [MessageHandler(filters.PHOTO, handle_photo_after)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()