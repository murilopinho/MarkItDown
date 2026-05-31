# Conversor para Markdown

Converte documentos **HTML, DOCX, PDF, CSV, XLSX e TXT** para Markdown com um clique.

Disponível como app desktop com interface gráfica (Windows/Linux) e como ferramenta de linha de comando.

---

## Funcionalidades

- Arraste e solte arquivos direto na janela
- Preview do Markdown gerado em tempo real
- Conversão em lote de vários arquivos de uma vez
- Botão para copiar o resultado ou abrir o arquivo salvo
- Fica na bandeja do sistema (não fecha, só minimiza)
- Configuração de pasta de destino persistente
- Detecção automática de encoding (UTF-8, Windows-1252, Latin-1)
- Suporte a listas, tabelas, headings e formatação no DOCX

---

## Formatos suportados

| Formato | Extensão |
|---------|----------|
| HTML    | `.html`, `.htm` |
| Word    | `.docx` |
| PDF     | `.pdf` (somente texto — PDFs escaneados retornam aviso) |
| Excel   | `.xlsx`, `.xls` |
| CSV     | `.csv` |
| Texto   | `.txt`, `.rst`, `.log` |

---

## Pré-requisitos

- **Python 3.10+** — [python.org/downloads](https://www.python.org/downloads/)
- pip (já vem com o Python)

---

## Instalação

**1. Clone o repositório**
```bash
git clone https://github.com/murilopinho/MarkItDown.git
cd MarkItDown
```

**2. Instale as dependências**
```bash
pip install -r requirements.txt
```

> No Linux, pode ser necessário instalar o tkinter separadamente:
> ```bash
> # Ubuntu/Debian
> sudo apt install python3-tk
> # Fedora
> sudo dnf install python3-tkinter
> ```

---

## Como usar

### Interface gráfica (recomendado)

```bash
python converter_app.py
```

1. Arraste arquivos para a janela **ou** clique em **+ Adicionar**
2. Clique em **▶ Converter**
3. Veja o preview no painel direito
4. Use **📋 Copiar** ou **📄 Abrir** para usar o resultado

![Screenshot da interface](https://via.placeholder.com/800x500?text=Screenshot+em+breve)

### Linha de comando

```bash
python convert_to_markdown_cli.py arquivo.pdf
python convert_to_markdown_cli.py planilha.xlsx -o resultado.md
python convert_to_markdown_cli.py documento.docx
```

**Instalar dependências automaticamente pela CLI:**
```bash
python convert_to_markdown_cli.py --install
```

**Ajuda:**
```bash
python convert_to_markdown_cli.py --help
```

### Como módulo Python

```python
from converter_core import convert_file

markdown, caminho_salvo = convert_file("documento.docx")
print(markdown)
```

---

## Estrutura do projeto

```
MarkItDown/
├── converter_app.py          # Interface gráfica (customtkinter)
├── converter_core.py         # Lógica de conversão (sem dependência de GUI)
├── convert_to_markdown_cli.py# Ferramenta de linha de comando
├── requirements.txt          # Dependências
└── icon.ico                  # Ícone do app
```

O `converter_core.py` é independente de GUI — pode ser importado em outros projetos ou adaptado para Android.

---

## Dependências principais

| Biblioteca | Uso |
|------------|-----|
| `customtkinter` | Interface gráfica moderna |
| `tkinterdnd2` | Drag & drop |
| `pystray` | Ícone na bandeja do sistema |
| `Pillow` | Geração do ícone |
| `html2text` | Conversão HTML → Markdown |
| `python-docx` | Leitura de arquivos Word |
| `pdfminer.six` | Extração de texto de PDF |
| `pandas` + `openpyxl` | Leitura de CSV e Excel |

---

## Licença

MIT — livre para usar, modificar e distribuir.
