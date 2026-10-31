# R-06. Прогон на VM во время оценки

Все команды выполняет оператор на VM организаторов из корня репозитория, в **Bash**.
Агент разбирает присланный вывод. Репетиция R-04 на VM пока не выполнена.
Генерации выполняются последовательно. Адрес и модель Qwen остаются фиксированными.

## 1. До слота: R-01 и демонстрационный ключ

Подготовить checkout согласованного коммита базовой ветки с G-01 и исправлениями,
уже проверенными на VM. Во время слота не обновлять ветку автоматически.

```bash
bash
set +x
set -o pipefail
umask 077
git status --short
git rev-parse HEAD
python3 --version
```

Нужен Python 3.12+. Если окружение ещё не подготовлено:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install -e '.[dev]'
```

Если `.venv` уже готова, достаточно `source .venv/bin/activate`.
Перед официальной генерацией **заменить тренировочный API-ключ демонстрационным**:

```bash
export QWEN_BASE_URL=http://10.10.10.10:4000/v1
unset QWEN_API_KEY
read -r -s -p 'Демонстрационный ключ Qwen: ' QWEN_API_KEY
printf '\n'
export QWEN_API_KEY
python - <<'PY'
from generator.config import Settings
settings = Settings.from_env()
assert settings.api_key, 'Не введён демонстрационный ключ'
print('Qwen: настройки проверены; значение ключа не выводится')
PY
python main.py index knowledge/sources
docker compose version
docker info --format '{{.ServerVersion}}'
```

`indexed_chunks` должен быть больше нуля. Docker предпочтительно доступен через группу
`docker`. Если оператору нужен sudo, проверить доступ командой
`sudo docker info --format '{{.ServerVersion}}'`, а в разделе 5 использовать вариант
`verify ... --sudo`. Пароль вводится в терминале, не в командной строке.
Не выполнять `env`, `set`, `cat .env`, `docker compose config` без `--quiet`.
Ключ не записывать в файлы, историю команд, отчёты или чат.

## 2. Бриф жюри → файл

Только после выдачи задания жюри. Новый официальный бриф использует новый каталог
`runs/case2`, без артефактов парковки или inventory. Если каталог уже существует,
сначала выяснить, относится ли он к этому же брифу; не удалять и не перезаписывать его.

```bash
mkdir -p runs
mkdir runs/case2
cat > runs/case2/requirements.md
```

Вставить точный текст брифа и нажать **Ctrl-D**. Не вставлять секреты. Для выданного
UTF-8 Markdown/текстового файла вместо `cat` скопировать его в этот же путь.

```bash
sha256sum runs/case2/requirements.md
export RWB_OUTPUT=runs/case2
export RWB_SLOT=runs/evaluation
mkdir -p "$RWB_SLOT"
cp -n "$RWB_OUTPUT/requirements.md" "$RWB_SLOT/requirements-original.md"
```

Зафиксированный бриф не редактировать. Уточнения идут отдельным JSON. Пайплайн
сравнивает хэш требований с `.pipeline/input.sha256` и отклоняет другой бриф в том же
каталоге. В журнале ниже сохраняется также SHA-256 исходного файла.

## 3. Учёт ID и предел трёх генераций

Выполнить определение функции один раз в текущем Bash. При повторном входе в shell
заново активировать `.venv`, задать `RWB_OUTPUT`, `RWB_SLOT` и определить функцию.
Существующий журнал сохранять. Во время официального слота все вызовы `generate`
выполнять через эту функцию.

Лимит жюри относится к полным попыткам, а не к числу вызовов модели. Для слота
используем консервативный предел: **не более трёх вызовов CLI `generate`, включая
продолжение с ответами и неуспешные вызовы**. Это не позволяет превысить три полные
попытки. Каждый вызов получает отдельный ID, а каталог и кэш сохраняются.
Внутренние HTTP-повторы, обращения ролей и ограниченные починки учитывать отдельно
по `.pipeline/events.jsonl`; их нельзя выдавать за отдельные полные генерации.
`RWB_MAX_REPAIRS` и остальные ограничения не менять.

```bash
rwb_generate() {
    local run_id run_log rc
    run_id=$(python - "$RWB_OUTPUT" "$RWB_SLOT" "$@" <<'PY'
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

output, slot = map(Path, sys.argv[1:3])
extra = sys.argv[3:]
if extra and (len(extra) != 2 or extra[0] != '--answers'):
    raise SystemExit('Допустим только --answers <путь>')
answers_hash = hashlib.sha256(Path(extra[1]).read_bytes()).hexdigest() if extra else None
journal = slot / 'generations.jsonl'
entries = [json.loads(row) for row in journal.read_text().splitlines()] if journal.exists() else []
if len(entries) >= 3:
    raise SystemExit('STOP: три вызова generate уже зарегистрированы')
number = len(entries) + 1
now = datetime.now(UTC)
run_id = f"case2-g{number:02}-{now:%Y%m%dT%H%M%S%fZ}"
record = {
    'run_id': run_id, 'number': number, 'started_at': now.isoformat(),
    'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'output': str(output),
    'requirements_sha256': hashlib.sha256((output / 'requirements.md').read_bytes()).hexdigest(),
    'answers_sha256': answers_hash,
}
run_log = slot / run_id
run_log.mkdir()
(run_log / 'start.json').write_text(json.dumps(record, indent=2) + '\n')
with journal.open('a') as stream:
    stream.write(json.dumps(record) + '\n')
print(run_id)
PY
    ) || return 1
    run_log="$RWB_SLOT/$run_id"
    printf 'RUN_ID=%s\n' "$run_id"
    if python main.py generate "$RWB_OUTPUT/requirements.md" --output "$RWB_OUTPUT" "$@" \
        2> "$run_log/generate.stderr.log" | tee "$run_log/generate.stdout.json"; then
        rc=0
    else
        rc=$?
    fi
    printf '%s\n' "$rc" > "$run_log/exit-code.txt"
    date -u +%FT%TZ > "$run_log/finished-at.txt"
    if [ -d "$RWB_OUTPUT/reports" ]; then
        cp -R "$RWB_OUTPUT/reports" "$run_log/reports"
    fi
    if [ -f "$RWB_OUTPUT/.pipeline/graph-state.json" ]; then
        cp "$RWB_OUTPUT/.pipeline/graph-state.json" "$run_log/graph-state.json"
    fi
    printf 'RUN_ID=%s EXIT_CODE=%s\n' "$run_id" "$rc"
    if [ "$rc" -ne 0 ]; then
        cat "$run_log/generate.stderr.log"
    fi
    return "$rc"
}
```

Первый запуск, без выдуманных заранее ответов:

```bash
rwb_generate
```

Зафиксировать напечатанный `RUN_ID`. Код 0 ещё не доказывает завершение:
`needs_clarification` тоже возвращается с кодом 0. Проверить `status` в выводе.
`generated_unverified` означает, что нужны сборка и проверка из раздела 5.
При `failed` или traceback остановиться и прислать агенту ID и вывод, не запускать
следующую генерацию вслепую. Отчёты, скопированные после раннего сбоя, могут относиться
к предыдущему вызову: актуальны stdout/stderr и события с текущим временем старта.

## 4. Обработка `needs_clarification`

Источник вопросов — массив объектов в `runs/case2/docs/clarifications.json`.
Показать жюри реальные вопросы, сохраняя их ID:

```bash
python -m json.tool "$RWB_OUTPUT/docs/clarifications.json"
```

Создать или дополнить JSON ответов интерактивно. Команда берёт ID из файла,
сохраняет прежние ответы и не подставляет ответы самостоятельно:

```bash
python - "$RWB_OUTPUT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
questions = json.loads((root / 'docs/clarifications.json').read_text(encoding='utf-8'))
path = root / 'answers.json'
answers = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
with open('/dev/tty', 'r+', encoding='utf-8', buffering=1) as terminal:
    for question in questions:
        terminal.write(json.dumps(question, ensure_ascii=False) + '\nОтвет жюри: ')
        answer = terminal.readline().strip()
        if not answer:
            raise SystemExit('Пустой ответ: сначала получить уточнение у жюри')
        answers[question['id']] = answer
path.write_text(json.dumps(answers, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'Ответы сохранены: {path}')
PY
python -m json.tool "$RWB_OUTPUT/answers.json"
rwb_generate --answers "$RWB_OUTPUT/answers.json"
```

Формат — объект `{"Q-001": "Ответ жюри", "Q-002": "Другой ответ"}`, значения —
непустые строки, ключи — только реальные ID вопросов. Ни бриф, ни анализ вручную
не исправлять. Продолжение использует тот же output и `.pipeline/checkpoints`;
готовый анализ переиспользуется. Ответы также сохраняются пайплайном в
`docs/clarification-answers.json`. Кэш используется только при совпадении отпечатка
входа этапа; изменение ответов не обещает попадания всех следующих этапов в кэш.
При последующих повторах передавать **тот же полный файл ответов**, не опускать
`--answers`. Если остались вопросы, повторить этот раздел в пределах общего лимита.
После третьего вызова новые генерации не запускать; сохранить результат и ограничения.

## 5. Конфигурация, verify и показ

После завершённой генерации создать локальные секреты приложения, только если
`.env` ещё отсутствует. Это отдельные учётные данные приложения, не Qwen API-ключ.

```bash
if [ ! -f "$RWB_OUTPUT/.env" ]; then
    python "$RWB_OUTPUT/scripts/configure.py"
fi
RWB_VERIFY_ID="verify-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$RWB_SLOT/$RWB_VERIFY_ID"
git rev-parse HEAD > "$RWB_SLOT/$RWB_VERIFY_ID/commit.txt"
printf '%s\n' "$RWB_OUTPUT" > "$RWB_SLOT/$RWB_VERIFY_ID/output.txt"
tail -n 1 "$RWB_SLOT/generations.jsonl" > "$RWB_SLOT/$RWB_VERIFY_ID/generation.json"
date -u +%FT%TZ > "$RWB_SLOT/$RWB_VERIFY_ID/started-at.txt"
python main.py verify "$RWB_OUTPUT" --execute --deploy \
    2>&1 | tee "$RWB_SLOT/$RWB_VERIFY_ID/verify.log"
RWB_VERIFY_RC=$?
printf '%s\n' "$RWB_VERIFY_RC" > "$RWB_SLOT/$RWB_VERIFY_ID/exit-code.txt"
date -u +%FT%TZ > "$RWB_SLOT/$RWB_VERIFY_ID/finished-at.txt"
cp -R "$RWB_OUTPUT/reports" "$RWB_SLOT/$RWB_VERIFY_ID/reports"
```

Если нужен sudo, заменить **только строку запуска verify** на:

```bash
python main.py verify "$RWB_OUTPUT" --execute --deploy --sudo \
    2>&1 | tee "$RWB_SLOT/$RWB_VERIFY_ID/verify.log"
```

Остальные команды учёта выполнить так же. Повтор `verify` не обращается к модели
и не расходует генерацию, но сохраняется с новым `RWB_VERIFY_ID`.
Уже работающий подготовительный compose-проект может занимать 8080: остановить
именно его до deployment, например `docker compose -f runs/inventory/docker-compose.yml stop`.
Тома не удалять.

```bash
python -m json.tool "$RWB_OUTPUT/reports/checks.json"
python -m json.tool "$RWB_OUTPUT/reports/summary.json"
curl --fail --silent --show-error --output /dev/null http://localhost:8080/
curl --fail --silent --show-error --output /dev/null http://localhost:8080/openapi/v1.json
```

Ожидаются `passed` для `structure`, `compose-config`, `dependency-lock`,
`backend-dependency-lock`, `build`, `unit`, `dependency-audit`, `deployment`, `acceptance`.
`not_run` не является успехом. Проверять также трассировку требований и готовность
релиза в summary: успешная сборка не доказывает покрытие всех требований.
Документы D-01 и сводку метрик D-02 учитывать только при их фактическом наличии.
Отсутствующие отчёты не заменять утверждением об успехе.

Для браузера на рабочей машине оператор открывает туннель к своему известному
SSH-адресу VM: `ssh -L 8080:localhost:8080 <VM>`. Затем открыть
`http://localhost:8080/` и `/swagger/index.html`. Токены приложения оператор вводит
локально; их не пересылать агенту и не включать в скриншоты.

## 6. Свидетельства, сбои и репетиция

Сохранить исходный бриф, `answers.json`, ID и время каждого вызова, SHA коммита,
журнал `runs/evaluation/generations.jsonl`, stdout/stderr и отдельные снимки отчётов.
В output сохранить `docs/analysis.json`, `docs/clarifications.json`, blueprint,
документы, исходники, тесты, всю `.pipeline` с событиями, ответами модели, кэшем и
профилями источников, `reports/*.json` и доступные метрики. `.pipeline` содержит
несколько запусков: границы задают `run_started`, временные метки и операторские ID.
Сама текущая версия пайплайна не назначает независимый UUID каждому полному прогону.

В чат передавать ID, безопасный вывод команды и конкретную ошибку. Не отправлять
`.env`, ключи, личные настройки, весь run-каталог или архив с секретами.
Агент отвечает: причина одной строкой → минимальное исправление с тестом → ruff и
pytest → коммит `R-fix: <кратко>` → точная команда повтора. Причины в
`generator/templates/` передаются пакету 2 с описанием правки; здесь шаблоны не меняются.
Проверки и лимиты сохраняются, push не выполняется. Исправление генератора доставляет
оператор согласованным способом; при повторе в журнал попадает новый SHA.

Репетиция R-04 выполняется **до замены ключа демонстрационным** на отдельном пути:

```bash
python main.py generate examples/inventory.md --output runs/inventory
```

При уточнениях задать `RWB_OUTPUT=runs/inventory` и выполнить только команды чтения
вопросов и Python-блок ввода ответов из раздела 4. `rwb_generate` в репетиции не вызывать.
Затем повторить
`python main.py generate examples/inventory.md --answers runs/inventory/answers.json --output runs/inventory`.
После завершения выполнить:

```bash
if [ ! -f runs/inventory/.env ]; then
    python runs/inventory/scripts/configure.py
fi
python main.py verify runs/inventory --execute --deploy
```

При необходимости добавить `--sudo`. Для репетиции отдельно записать SHA, ID,
время, вывод и результаты. Она не заполняет официальный журнал трёх вызовов.
После реального успешного выполнения зафиксировать дату, ID и ссылки на отчёты;
до этого R-06 подготовлен как документ, но критерий репетиции остаётся открытым.
