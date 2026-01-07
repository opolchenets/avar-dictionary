import csv
import io
import unittest

from scripts.parse_phrasebook_csv import parse_line


class ParsePhrasebookCsvTests(unittest.TestCase):
    def test_parse_line_with_repeated_index(self):
        line = "221. Дица гьеб цебе гӀадин гӀемер гьабуларо.,221. I don’t do that as often as I used to."
        text, translation = parse_line(line, 1)

        self.assertEqual(text, "Дица гьеб цебе гӀадин гӀемер гьабуларо.")
        self.assertEqual(translation, "I don’t do that as often as I used to.")

    def test_parse_line_with_embedded_quotes(self):
        line = '223. Томица гӀемераб магъакь-кӏачар гӏодорехизе ккола.,223. ""Tom needs to get rid of a lot of junk."""'
        text, translation = parse_line(line, 1)

        self.assertEqual(text, "Томица гӀемераб магъакь-кӏачар гӏодорехизе ккола.")
        self.assertEqual(translation, 'Tom needs to get rid of a lot of junk.')

    def test_parse_line_with_csv_reader(self):
        line = '"230. Дица гьеб гьабсагӀатго гьабилаан, дун мун вукӀаравани.","230. I would do that at once if I were you."'
        text, translation = parse_line(line, 1)

        self.assertEqual(text, "Дица гьеб гьабсагӀатго гьабилаан, дун мун вукӀаравани.")
        self.assertEqual(translation, "I would do that at once if I were you.")

    def test_parse_line_with_double_quotes_pattern(self):
        line = '"225. Дир хьул буго Бостоналде ине рес щвайгийилан.",225,""I hope I get a chance to go to Boston."""'
        text, translation = parse_line(line, 1)

        self.assertEqual(text, "Дир хьул буго Бостоналде ине рес щвайгийилан.")
        self.assertEqual(translation, "I hope I get a chance to go to Boston.")

    def test_csv_writer_round_trip(self):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["section", "text", "translation", "translit"])
        writer.writerow(["General", "Тест", "Test", ""])

        output.seek(0)
        rows = list(csv.reader(output))
        self.assertEqual(
            rows,
            [
                ["section", "text", "translation", "translit"],
                ["General", "Тест", "Test", ""],
            ],
        )


if __name__ == "__main__":
    unittest.main()
