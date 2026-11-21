# AI_Document_Intelligence_Agent

## Upload a document

`POST /documents/upload` accepts a single PDF or DOCX file smaller than 2 MiB.
The file is saved in the project `data/` directory, and its metadata is stored
in the PostgreSQL `documents` table. The table is created on the first valid
upload.

Configure PostgreSQL with `DATABASE_URL`, for example:

```text
postgresql+psycopg://<user>:<password>@localhost:5432/<database>
```

Send a multipart request with a `file` field:

```text
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@report.pdf"
```
