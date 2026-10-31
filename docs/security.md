# Безопасность: меры пайплайна и сгенерированного приложения

Документ сопоставляет контракт безопасности команды с кодом репозитория. Основа — раздел 4 [плана работ](workplan.md); номера «§» в колонках ниже взяты из строк плана, сам контракт в репозитории не хранится. Описано состояние на ревизию `03e0951` (база — ветка `codex/pipeline-quality-gates`).

Как читать статусы:

- ✅ — реализовано в коде; указаны тест или место, где это видно при чтении.
- ⚠️ — реализовано частично или есть оговорка.
- ❌ — не реализовано; указана задача плана.

Ни одна мера приложения и контейнеров не подтверждена прогоном на VM: полного прогона ещё не было ([status.md](status.md)). Строки со статусом ✅ означают «код и шаблон на месте», а не «проверено в работе». Свидетельства прогона появятся в `docs/evidence/<run-id>/` после R-02 и R-03.

## 1. Модель угроз

Недоверенными считаются: бриф, файл ответов `--answers`, файлы данных (`backend/data`), тексты регламентов из индекса, ответы модели и сгенерированный код. Доверенные части — фиксированные шаблоны платформы в [`generator/templates/`](../generator/templates), код генератора и фиксированные команды проверки.

Основные риски: инъекция инструкций через бриф или данные; выход генерации за каталог вывода; утечка ключа Qwen и паролей приложения; исполнение недоверенного кода; превышение бюджета токенов; слабая авторизация в сгенерированном приложении.

## 2. Пайплайн (генератор)

| Мера | Статус | Как реализована | Код | Проверка |
| --- | --- | --- | --- | --- |
| Только адрес и модель организаторов | ✅ | `Settings.from_env` отклоняет любой другой `QWEN_BASE_URL` и модель, отличную от `qwen3.8-27b` | [config.py](../generator/config.py) | прямого теста нет; проверяется чтением |
| Бриф, ответы, данные и найденные фрагменты — данные, не инструкции | ✅ запрет в промптах; ⚠️ теста на инъекцию нет | Системный промпт требует так читать регламенты. У ролей только три локальных инструмента: поиск по индексу, чтение разрешённого артефакта, загрузка навыка. Команд и сети в инструментах нет, раундов не больше двух | [llm.py](../generator/llm.py) (`SYSTEM`), [worker.py](../generator/worker.py) (`RoleAgent`, `TOOL_INSTRUCTION`) | `tests/test_worker.py`: чтение вне списка и защищённых путей отклоняется, неверные инструменты отклоняются. Тест на бриф с инъекцией — S-04 |
| Ссылки из брифа не открываются | ✅ | В пайплайне один HTTP-клиент, он обращается только к `base_url` из настроек и к `/utils/token_counter` того же адреса. Кода, который запрашивает URL из брифа, нет | [llm.py](../generator/llm.py), [budget.py](../generator/budget.py) | `grep -rn "httpx\." generator main.py` |
| Редиректы и прокси из окружения | ⚠️ | Редиректы выключены: так ведёт себя `httpx` по умолчанию. Прокси из переменных окружения не отключены (`trust_env` по умолчанию включён) | [llm.py](../generator/llm.py) | исправление и тест — S-01 |
| Лимиты и тип входных файлов | ❌ | `extract()` читает любой файл целиком; PDF определяется по расширению. Размер и тип по содержимому не проверяются | [knowledge.py](../generator/knowledge.py) | S-02, S-06 |
| Файл ответов `--answers` | ⚠️ | После анализа проверяется: JSON-объект, ключи только из известных `Q-nnn`, значения непустые строки. Ограничения размера нет | [pipeline.py](../generator/pipeline.py) (`Pipeline.analyst`) | S-02 |
| Ключ API не попадает в логи и отчёты | ✅ код; ⚠️ сквозного теста нет | Ключ идёт только в заголовок запроса. В событии сбоя HTTP он заменяется на `[REDACTED]`. В логах проверок скрываются значения переменных окружения с `TOKEN`, `PASSWORD`, `API_KEY` в имени и пароль sudo. Событие `model_completed` хранит `quota_identity` — SHA-256 от адреса и ключа, не сам ключ | [llm.py](../generator/llm.py), [verification.py](../generator/verification.py) (`run_check`) | `tests/test_verification.py::test_credentials_are_redacted_from_check_logs`; тест «ключа нет в файлах прогона» — S-04 |
| Пути вывода только внутри каталога | ✅ | Абсолютные пути, `..`, обратная косая, `:`, имена `.git`, `.ssh`, `node_modules`, `.env*` отклоняются. Итоговый путь обязан лежать внутри каталога вывода | [storage.py](../generator/storage.py) (`artifact_path`) | `tests/test_storage.py::test_generated_paths_cannot_escape_or_overwrite_credentials` (9 вариантов) |
| Модель пишет только файлы своего этапа | ✅ | `save_batch` требует, чтобы набор путей совпал с разрешённым для этапа; при несовпадении ничего не записывается | [storage.py](../generator/storage.py), [pipeline.py](../generator/pipeline.py) (`BACKEND_CONTRACT`, `FRONTEND`, `generate_files`) | `tests/test_storage.py::test_wrong_stage_files_are_rejected_before_any_writes` |
| CI, Dockerfile и compose пишет не Qwen | ✅ | Платформа копируется из шаблонов до генерации. Модель получает только списки файлов домена, тестов и документов | [pipeline.py](../generator/pipeline.py) (`Pipeline.run`), [templates/](../generator/templates) | чтением списков путей в `pipeline.py` |
| Проверки — только фиксированные команды | ✅ | Команды `docker compose …` заданы в коде; модель не выбирает команды и не меняет зависимости платформы | [verification.py](../generator/verification.py) | `tests/test_verification.py` |
| Невыполненная проверка не считается пройденной | ✅ | Без `--execute` статус `not_run`. Упавший процесс остаётся `failed`. Успешные строки тестов не отменяют неуспешный процесс приёмки | [verification.py](../generator/verification.py) | `test_skipped_execution_is_never_a_pass`, `test_failed_process_remains_failed`, `test_positive_test_lines_do_not_override_an_unsuccessful_acceptance_process` |
| Требование «пройдено» только при реальных свидетельствах | ✅ | Нужны: успешный контейнер приёмки, успешные именованные тесты `test_FR_nnn_*`, принятое независимое ревью утверждений с цитатой и привязка к файлам | [verification.py](../generator/verification.py) (`report`) | `test_runtime_success_without_independent_requirement_review_is_not_release_ready` и соседние тесты в `tests/test_verification.py` |
| Не больше двух починок, бюджеты токенов | ✅ | `RWB_MAX_REPAIRS=2`; счётчики починок принадлежат графу, роль не может их изменить. Ограничены минутный лимит (`RWB_TPM_LIMIT`), контекст, выход по этапам. Запрос, который не помещается в окно, отклоняется до отправки | [agents.py](../generator/agents.py) (`RoleGraph`), [budget.py](../generator/budget.py), [config.py](../generator/config.py) | `tests/test_agents.py` (починки), `tests/test_budget.py` |
| Выходной каталог привязан к брифу | ✅ | SHA-256 брифа записывается в `.pipeline/input.sha256`; запуск с другим брифом в том же каталоге завершается ошибкой | [pipeline.py](../generator/pipeline.py) (`Pipeline.run`) | чтением; отдельного теста нет |
| Продолжение по хэшам входов | ✅ | Кэш этапа назван по отпечатку промпта, схемы и модели. Повтор с теми же входами не вызывает модель | [llm.py](../generator/llm.py), [resume.py](../generator/resume.py) | `tests/test_llm.py`, `tests/test_resume.py`; повтор на практике — R-05 |
| Пароль sudo для Docker | ⚠️ | Читается через `getpass` или stdin, передаётся в `sudo -S` через stdin, маскируется в логах. Надёжнее добиться доступа через группу docker | [main.py](../main.py), [verification.py](../generator/verification.py) | `test_credentials_are_redacted_from_check_logs` |
| Секреты и исходные документы вне Git | ✅ | `.gitignore` исключает `.env*`, ключи, PDF, выгрузки переписки, `runs/`, индекс | [.gitignore](../.gitignore), [CONTRIBUTING.md](../CONTRIBUTING.md) | `git ls-files` |
| Сканирование секретов в репозитории пайплайна | ❌ | В GitHub CI нет сканера секретов | [ci.yml](../.github/workflows/ci.yml) | S-05 |
| CI самого генератора | ✅ | `ruff`, `pytest`, `pip_audit`; права `contents: read`; токен не сохраняется после checkout; запуск на self-hosted ранере только для PR из этого же репозитория | [ci.yml](../.github/workflows/ci.yml) | вкладка Actions |
| Зависимости пайплайна | ✅ | Версии зафиксированы в `requirements.lock`; `pip_audit` входит в CI | [requirements.lock](../requirements.lock) | `python -m pip_audit` |

## 3. Сгенерированное приложение

Платформенные файлы — фиксированные шаблоны из [`generator/templates/`](../generator/templates). Доменный код пишет Qwen; требования к нему заданы промптами и навыками, соблюдение проверяют ревью, сборка и приёмочные тесты.

| Мера | Статус | Как реализована | Код | Проверка |
| --- | --- | --- | --- | --- |
| Аутентификация по токенам | ✅ | Bearer-токены `ADMIN_TOKEN` и `DRIVER_TOKEN` из окружения. Сравнение за постоянное время. Роль, для которой токен не задан в конфигурации, не принимается. Токены создаёт `scripts/configure.py` (`secrets.token_urlsafe(32)`) в `.env`; фронтенд хранит введённый токен в `sessionStorage`, в сборку он не попадает | [Program.cs](../generator/templates/backend/Program.cs) (`TokenHandler`), [configure.py](../generator/templates/scripts/configure.py), [main.ts](../generator/templates/frontend/src/main.ts) | приёмочные тесты проекта (401); после прогона |
| Роли и политики | ✅ | Политики `admin` и `driver`; роль `admin` проходит политику `driver`. Маршруты домена обязаны вызывать `RequireAuthorization` — требование в промпте | [Program.cs](../generator/templates/backend/Program.cs), [backend-routes.md](../generator/prompts/backend-routes.md) | ревью backend и приёмочные тесты |
| Личность пользователя, проверка владельца | ⚠️ | Субъект равен роли (`admin` или `driver`): отдельных личностей водителей нет, проверка владельца сводится к сопоставлению со строкой роли. Промпт требует ограничивать записи по `OwnerSubject` | [Program.cs](../generator/templates/backend/Program.cs), [backend-service.md](../generator/prompts/backend-service.md) | A-06; до его готовности — известное ограничение |
| Единый формат ошибок RFC 7807 | ✅ | `AddProblemDetails`, обработчик исключений, коды без тела превращаются в problem details | [Program.cs](../generator/templates/backend/Program.cs), [DomainSupport.cs](../generator/templates/backend/DomainSupport.cs) (`OperationResult`) | приёмочные тесты проекта |
| Ограничение частоты запросов | ✅ | Политика `api`: 120 запросов в минуту на субъекта (при его отсутствии — на IP), ответ 429. Доменные маршруты обязаны подключать её — требование в промпте | [Program.cs](../generator/templates/backend/Program.cs) | после прогона |
| Идемпотентность критичных операций | ✅ | Ключ `Idempotency-Key` 8–128 допустимых символов, SHA-256 от маршрута и тела запроса, блокировка по паре «субъект + ключ», повтор возвращает сохранённый ответ, тот же ключ с другим телом — 409 | [DomainSupport.cs](../generator/templates/backend/DomainSupport.cs) (`RequestKeys.Execute`), [001_initial.sql](../generator/templates/backend/migrations/001_initial.sql) (`api_idempotency`) | приёмочные тесты: повтор и конфликт ключа — сверить на выводе R-03 |
| Аудит и outbox в одной транзакции | ✅ | Запись в `audit_events` и `outbox` одним SQL-выражением на том же соединении и в той же транзакции, что и изменение состояния; в событии `eventId`, `version`, `actor`, `occurredAt` | [DomainSupport.cs](../generator/templates/backend/DomainSupport.cs) (`DomainEvents.Append`), [Store.cs](../generator/templates/backend/Store.cs) | коммит `03e0951`; после прогона — тест повтора |
| Защита от повторной доставки событий | ⚠️ | Публикатор берёт строки через `FOR UPDATE SKIP LOCKED`, использует `acks=all` и идемпотентного продюсера, при сбое откатывает пачку. Доставка «минимум один раз»: потребитель обязан отсекать повторы по `eventId` ([ADR-004](architecture.md)) | [OutboxPublisher.cs](../generator/templates/backend/OutboxPublisher.cs) | R-03 |
| Здоровье и метрики | ⚠️ | `/health` и `/health/ready` возвращают `Healthy`, `Degraded` или `Unhealthy` по базе и Kafka (200 или 503); `/metrics` в формате Prometheus. Эндпоинты `/health*`, `/metrics`, `/openapi/*`, `/swagger/*` открыты без токена и проброшены через nginx на порт 8080; в метриках только счётчики | [Program.cs](../generator/templates/backend/Program.cs) (`ServiceHealth`, `ServiceMetrics`), [nginx.conf](../generator/templates/frontend/nginx.conf) | после прогона |
| Заголовки безопасности веб-сервера | ⚠️ | Есть `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`. `Content-Security-Policy` и `Permissions-Policy` нет | [nginx.conf](../generator/templates/frontend/nginx.conf) | A-04 |
| Контейнеры не от root | ✅ | Backend запускается как `USER app`, фронтенд — на `nginx-unprivileged`, образ юнит-тестов — `USER app` | [Dockerfile](../generator/templates/backend/Dockerfile), [frontend/Dockerfile](../generator/templates/frontend/Dockerfile), [backend-unit/Dockerfile](../generator/templates/backend-unit/Dockerfile) | `docker compose build` |
| Сеть и лимиты ресурсов | ✅ | Наружу публикуется только порт фронтенда; база, Kafka и backend доступны внутри сети compose. У каждого сервиса задан `mem_limit`. Kafka — один брокер, без TLS (прототип) | [docker-compose.yml](../generator/templates/docker-compose.yml) | `docker compose config` |
| Код Qwen исполняется только в контейнерах | ⚠️ | `unit` и `acceptance`: `read_only`, `cap_drop: [ALL]`, `no-new-privileges`, у приёмки каталог тестов монтируется только на чтение, сокета Docker нет. Сервисы `lock`, `backend-lock`, `audit` пока не ужесточены. Сборка образов — привилегированная операция доверенного оператора | [docker-compose.yml](../generator/templates/docker-compose.yml), [README](../README.md) (раздел Execution) | A-01 |
| Блокировка зависимостей | ✅ | Проверки `dependency-lock` и `backend-dependency-lock` создают файлы блокировки (`package-lock.json`, `packages.lock.json`); образы собираются через `npm ci` и `dotnet restore --locked-mode`. В `App.csproj` включены `NuGetAudit` и `TreatWarningsAsErrors` | [App.csproj](../generator/templates/backend/App.csproj), [Dockerfile](../generator/templates/backend/Dockerfile) | проверки `dependency-lock`, `backend-dependency-lock` |
| Сканирование уязвимостей и секретов | ✅ код; не выполнялось | Trivy 0.67.2, сканеры `vuln` и `secret`, уровни HIGH и CRITICAL, `--exit-code 1`, отчёт `reports/security.json`; файл `.env` исключён из сканирования намеренно | [docker-compose.yml](../generator/templates/docker-compose.yml) (сервис `audit`) | `verify --execute`: проверка `dependency-audit` |
| Статический анализ кода (SAST) | ❌ | Не реализован | — | A-02 |
| Образы по digest | ❌ | Образы заданы тегами, например `apache/kafka:4.1.0`, `postgres:17.9-bookworm`; digest не зафиксирован | [docker-compose.yml](../generator/templates/docker-compose.yml), Dockerfile | A-05 |
| Секреты приложения вне репозитория | ✅ | `.env` создаётся скриптом без перезаписи существующего и исключён в `.gitignore` и `.dockerignore`; в GitLab CI берётся из защищённой файловой переменной `APP_ENV_FILE` с правами `600` | [configure.py](../generator/templates/scripts/configure.py), [.gitlab-ci.yml](../generator/templates/.gitlab-ci.yml), [.gitignore](../generator/templates/.gitignore) | после прогона |
| SQL без конкатенации | ⚠️ | Платформенный код использует параметры. Для кода Qwen это требование промпта и ревью; машинной проверки (SAST) нет | [backend-service.md](../generator/prompts/backend-service.md), [backend-review.md](../generator/prompts/backend-review.md) | A-02 |
| Отрицательные приёмочные тесты | ⚠️ | Промпт требует: отказ на неверный ввод, запросы без токена, запрет админских методов для водителя, повтор критичных запросов. Состав реально сгенерированных тестов не проверен | [tests.md](../generator/prompts/tests.md), [assertion-review.md](../generator/prompts/assertion-review.md) | R-03: сверить вывод; пробелы — в `prompts/tests.md` |

## 4. Что открыто

| Задача плана | Что закроет |
| --- | --- |
| S-01 | прокси из окружения в HTTP-клиенте |
| S-02, S-06 | лимиты и тип входных файлов, ответы `--answers`, защита от zip-бомбы в DOCX |
| S-04 | сквозные тесты: ключ не попадает в файлы прогона; инъекция в брифе не исполняется |
| S-05 | сканирование секретов в CI генератора |
| A-01 | ужесточение сервисов `lock`, `backend-lock`, `audit` |
| A-02 | SAST |
| A-04 | CSP и Permissions-Policy |
| A-05 | образы по digest |
| A-06 | личности водителей и проверка владельца |
| R-03, R-05 | подтверждение мер приложения прогоном и повтор из кэша |

Срок и порядок задач — в [workplan.md](workplan.md). Сведения о результатах проверок конкретного прогона — в `docs/evidence/<run-id>/README.md`, а критерии оценки с адресами доказательств — в [evaluation-guide.md](evaluation-guide.md).

## 5. Как проверить

Меры пайплайна, для которых есть тесты:

```bash
.venv/bin/python -m pytest -q tests/test_storage.py tests/test_worker.py tests/test_verification.py tests/test_budget.py tests/test_agents.py tests/test_llm.py tests/test_resume.py
```

Зависимости и стиль, как в CI:

```bash
.venv/bin/python -m ruff check generator tests main.py
.venv/bin/python -m pip_audit
```

Меры приложения проверяются на сгенерированном проекте (`runs/<имя>`):

```bash
python main.py verify runs/parking --execute --deploy --sudo
python -m json.tool runs/parking/reports/summary.json
python -m json.tool runs/parking/reports/security.json | head -40
```

Файл `security.json` создаёт Trivy при выполнении проверки `dependency-audit`; по конфигурации проверка падает, если найдены уязвимости или секреты уровней HIGH и CRITICAL. Остальные отчёты описаны в [evaluation-guide.md](evaluation-guide.md).
