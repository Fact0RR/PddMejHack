package xlsx

import (
	"bytes"
	"fmt"

	"github.com/xuri/excelize/v2"
)


type Result struct {
	Crimes []struct {
		VideoName 	 string    `json:"video_name"`
		AmountOfFine int       `json:"amount_of_fine"`
		NameOfCrime  string    `json:"name_of_crime"`
		TimeOfFine   string `json:"time_of_fine"`
	} `json:"crimes"`
	VideoURL string `json:"video_url"`
	XlsxURL  string `json:"xlsx_url"`
}

func GenerateXLSX(data Result) (*bytes.Buffer, error) {
	f := excelize.NewFile()
	sheetName := "Sheet1"
	f.NewSheet(sheetName)

	headers := []string{"Название видео", "Название нарушения", "Сумма штрафа", "Время нарушения"}
	for i, header := range headers {
		cell := fmt.Sprintf("%s1", string(rune('A'+i)))
		f.SetCellValue(sheetName, cell, header)
	}

	for i, crime := range data.Crimes {
		f.SetCellValue(sheetName, fmt.Sprintf("A%d", i+2), crime.VideoName)
		f.SetCellValue(sheetName, fmt.Sprintf("B%d", i+2), crime.NameOfCrime)
		f.SetCellValue(sheetName, fmt.Sprintf("C%d", i+2), crime.AmountOfFine)
		f.SetCellValue(sheetName, fmt.Sprintf("D%d", i+2), crime.TimeOfFine)
	}

	buf := new(bytes.Buffer)
	if err := f.Write(buf); err != nil {
		return nil, err
	}
	return buf, nil
}