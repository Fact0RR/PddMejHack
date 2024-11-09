//генерация ключа для websocket
function getCurrentDateTimeFormatted() {
    const now = new Date();

    const year = now.getFullYear().toString();
    const month = String(now.getMonth() + 1).padStart(2, '0'); // Месяцы начинаются с 0
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const milliseconds = String(now.getMilliseconds()).padStart(3, '0'); // Добавлено для милисекунд

    return `${year}${month}${day}${hours}${minutes}${seconds}${milliseconds}`;
}

const GlobalKey = getCurrentDateTimeFormatted()

//подключение, как слушащий канал
let socket = new WebSocket("ws://localhost:8080/ws?type=0&key="+GlobalKey);

//уведомляем, что websocket подключен
socket.onopen = function(event) {
    console.log("connected");
};

//карта для названий колонок в результирующей таблице
let currentMap = new Map();

//измение карты, если присылается json другой структуры
function clearMapAndSetNewValues(keysArr,obj){
  currentMap.clear();
  reBuildTable(keysArr,obj);
  setNewValues(keysArr,obj);
}

//пересборка таблицы
function reBuildTable(keysArr,obj){
    const table = document.querySelector('table');
    while (table.rows.length) {
        table.deleteRow(0);
    }

    var head = document.createElement("tr")
    var body = document.createElement("tr")

    for (let i = 0;i< keysArr.length;i++){
        var th = document.createElement("th");
        var td = document.createElement("td");
        
        td.id = keysArr[i]

        th.textContent = keysArr[i]
        td.textContent = obj[keysArr[i]]

        head.appendChild(th);
        body.appendChild(td);
    }

    table.appendChild(head)
    table.appendChild(body)

}


function setNewValues(keysArr,obj){
  for (var i = 0;i<keysArr.length;i++)
  {
      currentMap.set(keysArr[i],obj[keysArr[i]])
  }
}

//установка таблицы
function setTable(obj){

    keysArr = Object.keys(obj);

    if (currentMap.size!==keysArr.length)
    {
        clearMapAndSetNewValues(keysArr,obj)
    }

    for (var i = 0;i<keysArr.length;i++)
    {
        if (currentMap.get(keysArr[i]) == null)
        {
            clearMapAndSetNewValues(keysArr,obj) 
        }
    }
    
    updateData(keysArr,obj)
}

function updateData(keysArr,obj){
    for (var i = 0;i<keysArr.length;i++)
    {
        document.getElementById(keysArr[i]).textContent = obj[keysArr[i]]
    }
}

//получение данных с сервера
socket.onmessage = function(event) {
    obj = JSON.parse(event.data);
    b64 = obj["b64"]

    if (b64!=undefined){
        //отрисовка изображения на экран
        document.getElementById("content").src = b64
        //удаление данных, чтобы код изображения не попал в таблицу
        delete(obj["b64"]);
    }

    setTable(obj);
};

document.getElementById('videoUploadForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Отменяем стандартное поведение формы

    const videoInput = document.getElementById('video');
    const message = document.getElementById('message');

    if (videoInput.files.length === 0) {
        message.textContent = 'Пожалуйста, выберите видео для загрузки.';
        message.style.color = 'red';
        return;
    }

    // Здесь вы можете добавить код для отправки видео на сервер (например, с использованием Fetch API)

    // // Для примера, просто показываем сообщение о успешной загрузке
    // message.textContent = 'Видео успешно загружено!';
    // message.style.color = 'green';

});

document.getElementById('uploadButton').addEventListener('click', uploadFile);

async function uploadFile() {
    const fileInput = document.getElementById('video');
    const file = fileInput.files[0];
    const outputImage = document.getElementById('outputImage');
    const message = document.getElementById('message');

    if (!file) {
        alert('Пожалуйста, выберите файл для загрузки.');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Ошибка при загрузке файла.');
        }
        return response.json();
    })
    .then(data => {
        // Проверяем тип файла
        message.textContent = 'Видео успешно загружено!';
        message.style.color = 'green';
        const type = file.type;
        if (type.startsWith('video/')) {
            console.log("video")
            url = '/data?url='+file.name+'&key='+GlobalKey; // Замените на адрес вашего изображения
            fetch(url, {
                method: 'GET', // Или 'POST' в зависимости от вашего API
                headers: {
                    'Content-Type': 'application/json' // Установите в случае необходимости
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json(); // Преобразуем ответ в JSON
            })
            .then(data => {
                console.log('Ответ от сервера:', data); // Выводим данные в консоль
                generateTable(data)
            })
            .catch(error => {
                console.error('Ошибка при отправке запроса:', error); // Обрабатываем ошибки
            });
        } else {
            alert('Выбранный файл не является видео или изображением.');
            return
        }

        outputImage.onload = function() { // Ждём загрузку изображения
            outputImage.scrollIntoView({ behavior: 'smooth', block: 'start' });
        };

    })
    .catch(error => {
        console.error('Ошибка:', error);
        alert('Произошла ошибка при загрузке.');
    });
}

function generateTable(data) {
    const tableContainer = document.getElementById('tableContainer');
    const table = document.createElement('table');
    table.className = 'table';

    // Заголовок таблицы
    const header = table.createTHead();
    const headerRow = header.insertRow();
    const th1 = document.createElement('th');
    th1.innerText = 'Описание';
    const th2 = document.createElement('th');
    th2.innerText = 'Ссылка';
    headerRow.appendChild(th1);
    headerRow.appendChild(th2);

    // Первая строка таблицы для видео
    const row1 = table.insertRow();
    const cell1a = row1.insertCell(0);
    cell1a.innerText = 'Обработанное видео';
    const cell1b = row1.insertCell(1);
    const videoLink = document.createElement('a');
    videoLink.href = data.video_url;
    videoLink.innerText = 'посмотреть ->';
    videoLink.target = '_blank'; // Открываем ссылку в новой вкладке
    cell1b.appendChild(videoLink);

    // Вторая строка таблицы для Excel файла
    const row2 = table.insertRow();
    const cell2a = row2.insertCell(0);
    cell2a.innerText = 'Excel файл';
    const cell2b = row2.insertCell(1);
    const excelLink = document.createElement('a');
    excelLink.href = data.xlsx_url;
    excelLink.innerText = 'скачать ->';
    //excelLink.target = '_blank'; // Открываем ссылку в новой вкладке
    cell2b.appendChild(excelLink);

    // Добавляем таблицу в контейнер
    tableContainer.innerHTML = ''; // Очищаем контейнер перед добавлением
    tableContainer.appendChild(table);
}

document.getElementById('zipuploadButton').addEventListener('click', uploadZipFile);

async function uploadZipFile() {
    const fileInput = document.getElementById('zip');
    const file = fileInput.files[0];
    const message = document.getElementById('message');

    if (!file) {
        alert('Пожалуйста, выберите файл для загрузки.');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    fetch('/uploadzip', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Ошибка при загрузке файла.');
        }
        return response.json();
    })
    .then(data => {
        // Проверяем тип файла
        message.textContent = 'Файл zip успешно загружен!';
        message.style.color = '#8e44ad';
        console.log(data)

        const uploadedFiles = data.uploaded_files; // Массив загруженных файлов

        // Подготавливаем объект для передачи
        const payload = { files: uploadedFiles };
    
        // Отправка нового POST-запроса с JSON
        return fetch('/datazip?key=' + encodeURIComponent(GlobalKey), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload) // Передаем JSON в body
        }).then(response => response.json()) // Преобразуем ответ в формат JSON
        .then(data => {
            console.log(data); // Выводим результат в консоль
            generateTable(data)
        })
        .catch(error => {
            console.error('Ошибка:', error); // Обработка ошибок
        });
    })
    .catch(error => {
        console.error('Ошибка:', error);
        alert('Произошла ошибка при загрузке.');
    });
}