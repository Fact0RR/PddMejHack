package handlers

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"server/handlers/xlsx"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/minio/minio-go/v7"
)

func (h Handler) UploadZIPs(c *gin.Context) {
    file, err := c.FormFile("file")
    if err != nil {
        c.String(http.StatusBadRequest, fmt.Sprintf("Failed to get file: %s", err.Error()))
        return
    }

    fileReader, err := file.Open()
    if err != nil {
        c.String(http.StatusInternalServerError, fmt.Sprintf("Failed to open file: %s", err.Error()))
        return
    }
    defer fileReader.Close()

    // Разархивируем .zip файл
    zipReader, err := zip.NewReader(fileReader, file.Size)
    if err != nil {
        c.String(http.StatusInternalServerError, fmt.Sprintf("Failed to read zip file: %s", err.Error()))
        return
    }

    var uploadedFiles []string

    // Обработка каждого файла в архиве
    for _, zf := range zipReader.File {
        if zf.FileInfo().IsDir() || !isVideoFile(zf.Name) {
            continue
        }

        rc, err := zf.Open()
        if err != nil {
            c.String(http.StatusInternalServerError, fmt.Sprintf("Failed to open zip file: %s", err.Error()))
            return
        }
        defer rc.Close()

        // Загружаем видеофайл в MinIO
        _, err = h.minio.PutObject(c, h.settings.Minio.BucketName, zf.Name, rc, zf.FileInfo().Size() , minio.PutObjectOptions{
            ContentType: "video/mp4", // Уточните Content-Type в зависимости от типа видеофайла
        })
        if err != nil {
            c.String(http.StatusInternalServerError, fmt.Sprintf("Failed to upload file to MinIO: %s", err.Error()))
            return
        }

        uploadedFiles = append(uploadedFiles, zf.Name) // Сохраняем название загруженного файла
    }

    c.JSON(http.StatusOK, gin.H{
        "uploaded_files": uploadedFiles, // Возвращаем список загруженных файлов
    })
}

// Функция для проверки, является ли файл видеофайлом
func isVideoFile(filename string) bool {
    videoExtensions := []string{".mp4", ".avi", ".mov", ".mkv", ".wmv"}
    for _, ext := range videoExtensions {
        if strings.HasSuffix(strings.ToLower(filename), ext) {
            return true
        }
    }
    return false
}

func (h Handler) DataZip(c *gin.Context) {

	rawKey := c.Query("key")
	if rawKey == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "key parameter is required"})
		return
	}


	encodedKEY := url.QueryEscape(rawKey)
	proxyURL := h.settings.Model.Endpoint + "/datazip?key=" + encodedKEY
	body:=proxyPost(c,proxyURL,"application/json")
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

func proxyPost(c *gin.Context, proxyURL string, contentType string) []byte {
    // Читаем тело запроса
    body, err := io.ReadAll(c.Request.Body)
    if err != nil {
        println("Ошибка при чтении тела запроса: ", err.Error())
        c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read request body"})
        return nil
    }
    
    // Возвращаем тело запроса на место, чтобы оно было доступно для других обработчиков
    c.Request.Body = io.NopCloser(bytes.NewBuffer(body))

    // Выполняем POST-запрос
    resp, err := http.Post(proxyURL, contentType, bytes.NewBuffer(body))
    if err != nil {
        println("Ошибка при отправке POST запроса: ", err.Error())
        c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to receive response from source"})
        return nil
    }
    defer resp.Body.Close()

    // Проверяем статус ответа
    if resp.StatusCode != http.StatusOK {
        println("Статус: ", resp.StatusCode)
        c.JSON(resp.StatusCode, gin.H{"error": "failed to post data"})
        return nil
    }

    // Читаем тело ответа
    responseBody, err := io.ReadAll(resp.Body)
    if err != nil {
        println("Ошибка при чтении тела ответа: ", err.Error())
        c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response body"})
        return nil
    }

    return responseBody
}