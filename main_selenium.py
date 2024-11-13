import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Загрузка данных о классах
def load_class_data(filename):
    with open(filename, "r", encoding="utf-8") as file:
        data = json.load(file)
    return {
        school_class["class_id"]: school_class["students"]
        for school_class in data["school"]["classes"]
    }

# Инициализация Selenium
def initialize_browser(path_to_driver):
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver_path = path_to_driver  
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def fetch_attempts_selenium(driver, url, class_students, classes_to_check=None):
    driver.get(url)
    
    # Явное ожидание загрузки таблицы попыток
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr.gradedattempt"))
        )
    except Exception as e:
        print("Не удалось дождаться загрузки попыток:", e)
        return []

    # Парсим HTML страницы попыток
    soup = BeautifulSoup(driver.page_source, "html.parser")
    attempts = []

    # Найдем все строки с попытками после загрузки страницы
    rows = soup.find_all("tr", class_="gradedattempt")
    if not rows:
        print("Не удалось найти попытки в HTML. Возможно, формат страницы изменился или сессия неактивна.")
        return attempts

    for row in rows:
        attempt_id_tag = row.find("input", {"name": "attemptid[]"})
        attempt_id = attempt_id_tag["value"] if attempt_id_tag else None

        # Проверка на наличие аватара
        user_name_tag = row.find("a", class_="d-inline-block aabtn")
        if user_name_tag:
            img_tag = user_name_tag.find("img")
            # Если аватарка есть, берем имя из атрибута `title` изображения
            if img_tag and "title" in img_tag.attrs:
                user_name = img_tag["title"]
            else:
                # Если аватарки нет, берем имя из `span`
                user_name_span = user_name_tag.find("span", {"title": True})
                user_name = user_name_span["title"] if user_name_span else None
        else:
            user_name = None

        # Определяем класс ученика
        student_class = None
        for class_id, students in class_students.items():
            if user_name in students:
                student_class = class_id
                break

        # Фильтруем по классам, если указаны классы для проверки
        if attempt_id and user_name and (not classes_to_check or student_class in classes_to_check):
            attempts.append({"attempt_id": attempt_id, "user_name": user_name, "class_id": student_class})

    return attempts

# Функция для получения решений по попыткам
def fetch_solutions_for_attempt(driver, attempt_id, user_name, class_id):
    # Открываем страницу попытки
    url = f"https://sdo24.1580.ru/mod/quiz/review.php?attempt={attempt_id}"
    driver.get(url)
    time.sleep(3)  # Ждем загрузки страницы

    # Парсим HTML страницы попытки
    soup = BeautifulSoup(driver.page_source, "html.parser")
    questions = soup.find_all("div", class_="que")

    solutions = []
    for question in questions:
        # Извлекаем номер вопроса
        question_number_tag = question.find("h3", class_="no")
        question_number = question_number_tag.text.split()[-1] if question_number_tag else "unknown"

        # Проверяем, прошел ли ответ все тесты
        is_correct = question.find("div", class_="coderunner-test-results good")
        if is_correct:
            code_area = question.find("textarea", class_="coderunner-answer")
            code = code_area.text if code_area else ""
            solutions.append((question_number, code))

    # Сохраняем решения, прошедшие все тесты
    if solutions:
        user_folder = f"solutions/{class_id}/{user_name}"
        os.makedirs(user_folder, exist_ok=True)
        for question_number, solution in solutions:
            solution_file = os.path.join(user_folder, f"solution_question_{question_number}.py")
            with open(solution_file, "w", encoding="utf-8") as file:
                file.write(solution)
        print(f"Сохранено решения у {user_name} (Попытка {attempt_id})")
    else:
        print(f"Нет решений, прошедших тесты, для попытки {attempt_id} у {user_name}")

# Основная логика
if __name__ == "__main__":
    quiz_id = "2732"  # Задайте нужный ID теста
    classes_to_check = ["10Е1", "10Е2","10З1","10З2"] # заменить на нужные классы (только проверьте полноту списка в файле class_data)
    path_to_driver = r"C:path/to/chromedriver.exe" # путь до драйвера свой
    class_data_file = "class_data.json"  # Путь к JSON-файлу с классами и учениками
    class_students = load_class_data(class_data_file)

    # Настройка URL и драйвера Selenium
    url = f"https://sdo24.1580.ru/mod/quiz/report.php?id={quiz_id}&mode=overview&attempts=enrolled_with"
    driver = initialize_browser(path_to_driver)

    # Вход в аккаунт Moodle
    print("Пожалуйста, выполните вход в открывшемся браузере.")
    driver.get("https://sdo24.1580.ru/login/index.php")
    input("Нажмите Enter после завершения входа...")

    print("Получаем попытки...")
    attempts = fetch_attempts_selenium(driver, url, class_students, classes_to_check=classes_to_check)

    if not attempts:
        print("Не удалось найти попытки для указанных классов.")
    else:
        print(f"Найдено {len(attempts)} попыток.")
        for attempt in attempts:
            fetch_solutions_for_attempt(driver, attempt["attempt_id"], attempt["user_name"], attempt["class_id"])

    driver.quit()