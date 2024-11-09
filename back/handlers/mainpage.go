package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"server/handlers/xlsx"
	"server/settings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

type Handler struct {
	minio    *minio.Client
	settings settings.Settings
}

func NewHomeHandler(settings settings.Settings) (Handler, error) {
	minioClient, err := minio.New(settings.Minio.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(settings.Minio.AccessKeyID, settings.Minio.SecretAccessKey, ""),
		Secure: false, // Установите true, если используете HTTPS
	})
	if err != nil {
		println(settings.Minio.Endpoint)
		println(err.Error())
		return Handler{}, err
	}

	return Handler{minio: minioClient, settings: settings}, nil
}

func (h Handler) Home(c *gin.Context) {
	c.HTML(
		// Установка статуса HTTP на 200
		http.StatusOK,
		// Использование index.html шаблона
		"index.html",
		// Установка title на "Home Page"
		gin.H{
			"title": "hackaton",
		},
	)
}

func (h Handler) Upload(c *gin.Context) {
	file, err := c.FormFile("file")
	if err != nil {
		println(http.StatusBadRequest, fmt.Sprintf("Failed to get file: %s", err.Error()))
		c.String(http.StatusBadRequest, fmt.Sprintf("Failed to get file: %s", err.Error()))
		return
	}

	// Открываем файл в памяти
	fileReader, err := file.Open()
	if err != nil {
		println(http.StatusInternalServerError, fmt.Sprintf("Failed to open file: %s", err.Error()))
		c.String(http.StatusInternalServerError, fmt.Sprintf("Failed to open file: %s", err.Error()))
		return
	}
	defer fileReader.Close()

	// Загрузка файла в MinIO
	_, err = h.minio.PutObject(c, h.settings.Minio.BucketName, file.Filename, fileReader, file.Size, minio.PutObjectOptions{
		ContentType: "video/mp4",
	})
	if err != nil {
		println(http.StatusInternalServerError, fmt.Sprintf("Failed to upload file to MinIO: %s", err.Error()))
		c.String(http.StatusInternalServerError, fmt.Sprintf("Failed to upload file to MinIO: %s", err.Error()))
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"file_name": file.Filename,
	})
}

func proxyGet(c *gin.Context, proxyURL string, contentType string) []byte{
	// Выполняем GET-запрос
	resp, err := http.Get(proxyURL)
	if err != nil {
		println("Ошибка при отправки GET запроса: ", err.Error())
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to receive response from source"})
		return nil
	}
	defer resp.Body.Close()

	// Проверяем статус ответа
	if resp.StatusCode != http.StatusOK {
		println("Статус: ", resp.StatusCode)
		c.JSON(resp.StatusCode, gin.H{"error": "failed to get video feed"})
		return nil
	}

	 // Читаем тело ответа
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		 println("Ошибка при чтении тела ответа: ", err.Error())
		 c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response body"})
		 return nil
	}

	return body
}


func (h Handler) Data(c *gin.Context) {
	rawURL := c.Query("url")
	if rawURL == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "url parameter is required"})
		return
	}
	rawKey := c.Query("key")
	if rawURL == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "key parameter is required"})
		return
	}

	// Кодируем URL
	encodedURL := url.QueryEscape(rawURL)
	encodedKEY := url.QueryEscape(rawKey)
	proxyURL := h.settings.Model.Endpoint + "/data?url=" + encodedURL + "&key=" + encodedKEY
	body := proxyGet(c,proxyURL,"application/json")
	var data xlsx.Result
    err := json.Unmarshal(body, &data)
    if err != nil {
        println("Ошибка при парсинге JSON: ", err.Error())
        c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to parse response body"})
        return
    }

	xlsxFile, err :=xlsx.GenerateXLSX(data)
	if err != nil{
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to generate xlsx"})
        return
	}

	urlxlsx, err := uploadToMinIO(c,h,xlsxFile)
	if err != nil{
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to upload xlsx to s3"})
        return
	}
	data.XlsxURL = urlxlsx

	c.JSON(http.StatusOK,data)
}


func uploadToMinIO(c *gin.Context, h Handler, body *bytes.Buffer) (string, error) {

	currentTime := time.Now()
    formattedTime := currentTime.Format("20060102150405")

   	// Загрузка файла в MinIO
	_, err := h.minio.PutObject(c, h.settings.Minio.BucketName, formattedTime, body, int64(body.Len()), minio.PutObjectOptions{
		ContentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	})
	if err != nil {
		println(http.StatusInternalServerError, fmt.Sprintf("Failed to upload file to MinIO: %s", err.Error()))
		return "",err
	}

    return fmt.Sprintf("http://%s/%s/%s", h.settings.Minio.Endpoint, h.settings.Minio.BucketName, formattedTime), nil
}