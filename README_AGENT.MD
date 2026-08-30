# GLTD Kid Control — README para Agentes (IA)

Este documento é a fonte de verdade para **agentes de IA** e desenvolvedores que
vão trabalhar neste repositório. Leia tudo antes de editar qualquer arquivo. Não
é documentação de usuário final — para isso veja [`README.md`](README.md) e
[`HOWTO.md`](HOWTO.md).

---

## 1. Objetivo

Controle parental auto-hospedado em uma LAN (Debian/Linux Mint + navegador Brave):

- Um **servidor** define perfis (por criança), listas de canais bloqueados/
  recomendados (CSV) e consulta o histórico de uso.
- Um **cliente** roda na máquina da criança, altera a interação com DNS, bloqueia
  navegadores não autorizados e reporta uso/histórico ao servidor.
- Uma **extensão** (Chrome/Brave) remodela o YouTube (remove Shorts/recomendações
  e bloqueia conteúdo conforme as listas do perfil).

Tudo roda dentro da rede do usuário. **Não há** servidor externo nem coleta de
dados por terceiros.

---

## 2. Arquitetura

```
                      +---------------------------+
                      |   SERVER (máquina admin)  |
                      |  gltd_kid_server (Python) |
                      |  - API HTTP (JSON)        |
                      |  - Web UI (local)         |
                      |  - MariaDB ou JSON        |
                      |  - DNS local (opcional)   |
                      +-------------+-------------+
                                    | LAN
                 +------------------+------------------+
                 |                                     |
       +---------v---------+              +------------v---------+
       | CLIENT (máquina)  |              | CLIENT (máquina)     |
       | gltd_kid_client   |              | gltd_kid_client      |
       | - enforce (proc)  |              | - enforce (proc)     |
       | - DNS local (5300)|              | - DNS local (5300)   |
       | - local HTTP 8877 |              | - local HTTP 8877    |
       | - Brave + extensão|              | - Brave + extensão   |
       +-------------------+              +----------------------+
```

### Fluxo de dados

1. Admin edita perfis/listas no servidor (arquivo de config ou painel web).
2. `lists/` contém os CSVs de bloqueio/permissão — fonte de dados real.
3. O cliente busca as listas do seu perfil em `GET /api/client/lists?token=...`,
   monta um cache local e aplica a filtragem (extensão + DNS + processos).
4. O cliente reporta em `POST /api/client/report` (uso, urls, histórico do YouTube)
   e envia heartbeat em `POST /api/client/heartbeat`.
5. O admin acompanha pelo painel (`/`) e pela API.

### Decisões técnicas

- Python 3.10+; o servidor HTTP usa **apenas stdlib** (`http.server`, `json`,
  `csv`, `urllib`). Sem Flask/FastAPI.
- Persistência: **MariaDB** via `pymysql` (tabelas `profiles`, `history`,
  `app_usage`, `url_log`, `settings`, `client_heartbeat`) com fallback **JSON**
  (arquivos em `data_dir`).
- Config em **JSON** (`/etc/gltd-kid-control/config.json` em produção).
- Listas em **CSV** (`lists/`).

---

## 3. Estrutura de pastas

```
gltd_kid_control/
├── README.md                # documentação para humanos
├── HOWTO.md                 # instalação/uso
├── README_AGENT.MD          # este arquivo (agentes/IA)
├── LICENSE                  # Apache-2.0
├── .gitignore               # exclui dados sensíveis (ver §9)
├── lists/                   # listas CSV (fonte de dados real)
│   ├── block_child1.csv
│   ├── block_child2.csv
│   ├── block_baixa_cultura.csv
│   ├── allow_child1.csv
│   └── allow_child2.csv
├── config/
│   └── server.example.json  # exemplo de configuração do servidor
├── icons/                   # ícones do projeto
├── extension/               # extensão (escopo futuro — ver client/extension)
├── server/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── bin/gltd-kid-server
│   ├── sql/schema.sql
│   ├── docs/{ARCHITECTURE,API,PACKAGING}.md
│   ├── scripts/
│   │   ├── first_run.py     # assistente de primeira execução
│   │   ├── dns_server.py    # DNS local (bloqueio de domínios)
│   │   ├── install.sh       # instalação manual (dev)
│   │   ├── build_deb.sh     # gera .deb
│   │   ├── server_start.sh / server_stop.sh
│   │   ├── dns_start.sh
│   │   ├── start_admin.sh   # sobe server + abre painel
│   │   └── tray.py          # ícone de status (Cinnamon)
│   └── gltd_kid_server/
│       ├── __init__.py / _version.py
│       ├── __main__.py      # entrypoint CLI
│       ├── config.py        # ServerConfig + load/save JSON
│       ├── models.py        # dataclasses: ChannelEntry, Profile, HistoryEntry
│       ├── lists.py         # leitura/validação dos CSVs
│       ├── db.py            # Store: MariaDBStore + JsonStore
│       ├── auth.py          # hash PBKDF2 + sessões por token
│       ├── api.py           # KidControlServer + endpoints HTTP
│       └── web/             # UI estática (login/setup/dashboard/profile/settings)
└── client/
    ├── README.md
    ├── bin/gltd-kid-client
    ├── extension/           # manifest.json, content.js, popup.html, icons
    ├── keys/                # chave privada da extensão (ignorada pelo git)
    ├── scripts/
    │   ├── make_crx.py      # empacota extensão em CRX3
    │   ├── build_deb.sh     # gera .deb do client
    │   ├── postinst         # pós-instalação (systemd + extensão)
    │   └── gltd-kid-client.service
    └── gltd_kid_client/
        ├── __init__.py / _version.py
        ├── __main__.py      # CLI: setup | daemon | once | status
        ├── config.py        # ClientConfig (/etc/gltd-kid-control/client.json)
        ├── core.py          # loop do daemon (enforce + report + status)
        ├── enforce.py       # bloqueio de navegadores + iptables DNS redirect
        ├── dns.py           # DNS local do client (127.0.0.1:5300)
        ├── localserver.py   # HTTP local (127.0.0.1:8877) p/ extensão
        ├── reporter.py      # comunicação HTTP com o servidor
        ├── brave_history.py # leitura do histórico do Brave (SQLite)
        ├── auth.py          # verificação de senha (PBKDF2)
        └── tray.py          # ícone de status (bandeja)
```

---

## 4. Esquema dos CSVs (listas)

As listas são a fonte de dados real. O tipo (block/allow) é detectado pelo
cabeçalho em `lists.py` (`_detect_kind`).

### Listas de bloqueio (`block_*.csv`)

Cabeçalho:

```
handle,nome_canal,url,categoria,motivo_bloqueio,nivel_risco,alternativa_saudavel
```

| campo | descrição |
|---|---|
| handle | `@handle` do canal (sem espaços) |
| nome_canal | nome amigável |
| url | `https://www.youtube.com/@handle` |
| categoria | ver catálogo abaixo |
| motivo_bloqueio | razão (livre, concisa) |
| nivel_risco | `alto` ou `medio` |
| alternativa_saudavel | categoria de canal permitido sugerido |

### Listas de recomendação (`allow_*.csv`)

Cabeçalho:

```
handle,nome_canal,url,categoria,beneficio,idioma
```

| campo | descrição |
|---|---|
| handle | `@handle` |
| nome_canal | nome amigável |
| url | URL completa |
| categoria | tema |
| beneficio | por que é recomendado |
| idioma | `portugues`, `ingles`, etc. |

### Categorias de bloqueio

`namoro_relacionamento`, `adultizacao`, `adultizacao_arte`,
`adultizacao_sexualizacao`, `adultizacao_beauty`, `adultizacao_romance`,
`derrete_cerebro`, `pauta_lgbt_genero`, `conteudo_adulto`, `funk_brasileiro`,
`funk_pop`, `sertanejo`, `forro_sertanejo`, `brainrot`,
`adulto_fingindo_crianca`, `identitarismo_lgbtq`, `kpop`, `canal`, `video`,
`url`, `dominio`, `manual`.

> Categorias especiais `video`, `url`, `dominio` são usadas pelos bloqueios
> manuais gerados pela API (arquivo `block_manual_<id>.csv`).

> **Atenção:** os `handle`/`url` das listas são **sugestões** que precisam de
> validação antes de uso em produção.

---

## 5. Modelos de dados (`models.py`)

- `ChannelEntry`: `handle, nome_canal, url, categoria, info, extra, extra2`.
  (`info` = motivo_bloqueio **ou** beneficio; `extra` = nivel_risco **ou**
  idioma; `extra2` = alternativa_saudavel, só em block.)
- `Profile`: `id, name, lan_ip, linux_user, allowed_browsers, block_lists,
  allow_lists, filters, client_token`.
- `HistoryEntry`: `id, profile_id, channel_handle, channel_name, video_title,
  video_url, thumb_url, description, watched_at`.

---

## 6. API HTTP (servidor)

Base: `http://<server>:8123`. Autenticação por cookie de sessão (`kid_sid`),
com exceção das rotas públicas (`/api/health`, `/api/setup/status`, `/api/setup`,
`/api/login`) e das rotas de client autenticadas por `token`.

### Públicas / setup / login

| método | rota | descrição |
|---|---|---|
| GET | `/api/health` | `{status, version}` |
| GET | `/api/setup/status` | `{setup_done}` |
| POST | `/api/setup` | cria admin (user+senha), marca setup_done |
| POST | `/api/login` | autentica e cria sessão |

### Admin (sessão)

| método | rota | descrição |
|---|---|---|
| GET | `/api/me` | usuário logado |
| GET | `/api/profiles` | lista perfis |
| GET | `/api/profiles/{id}` | um perfil ou `404` |
| GET | `/api/profiles/{id}/summary` | resumo (histórico, uso, urls, heartbeat) |
| GET | `/api/profiles/{id}/usage` | uso de apps |
| GET | `/api/profiles/{id}/urls` | urls navegadas |
| GET | `/api/profiles/{id}/youtube` | histórico do YouTube |
| POST | `/api/profiles` | cria perfil |
| PUT | `/api/profiles/{id}` | atualiza perfil |
| DELETE | `/api/profiles/{id}` | remove perfil |
| POST | `/api/profiles/{id}/block-{channel\|video\|url\|domain}` | bloqueio manual |
| GET | `/api/lists` | resumo das listas |
| GET | `/api/lists/files` | arquivos de lista |
| POST | `/api/lists/upload` | sobe/valida um CSV |
| GET | `/api/history?profile=&limit=` | histórico |
| POST | `/api/history` | adiciona histórico |
| POST | `/api/usage` | adiciona uso de app |
| POST | `/api/urls` | adiciona url |
| POST | `/api/filters` | adiciona expressão de bloqueio a um perfil |
| GET/PUT | `/api/settings` | configurações do sistema |
| POST | `/api/admin/password` | troca a senha do admin |
| POST | `/api/logout` | encerra a sessão |

### Client (token por perfil)

| método | rota | descrição |
|---|---|---|
| GET | `/api/client/lists?token=` | listas do perfil + dados (com `admin_password_hash` p/ pausa offline) |
| POST | `/api/client/report` | reporta `{usage, urls, history}` |
| POST | `/api/client/heartbeat` | `{mode, active, server_ok}` |

Ver também `server/docs/API.md`.

---

## 7. Componentes do servidor

- **`config.py`**: `ServerConfig` (dataclass) + `load_config`/`save_config`/
  `ensure_dirs`. Caminhos padrão: `APP_DIR = /var/lib/gltd-kid-control`,
  `DEFAULT_LISTS_DIR = <repo>/lists`.
- **`db.py`**: interface `Store` com duas implementações:
  - `MariaDBStore`: cada operação abre a própria conexão (thread-safe via lock);
    cria o schema (`_SCHEMA`) no `__init__`.
  - `JsonStore`: arquivos JSON em `data_dir` (`profiles.json`,
    `history/<data>.json`, `usage/<data>.json`, `urls/<data>.json`).
  - `create_store(cfg)` escolhe por `cfg.db_backend`.
- **`auth.py`**: `hash_password`/`verify_password` (PBKDF2-SHA256, 200k iterações)
  e `SessionManager` (sessões em memória, TTL 24h).
- **`api.py`**: `KidControlServer(ThreadingHTTPServer)` + `KidControlAPI`
  (`BaseHTTPRequestHandler`). Rotas em `do_GET/do_POST/do_PUT/do_DELETE`.

---

## 8. Componentes do cliente

O cliente roda como **daemon root** (systemd `gltd-kid-client.service`), para
que a criança não consiga encerrá-lo.

- **`core.py`** — loop principal (`run_daemon`):
  1. inicia servidor HTTP local (`localserver`, 8877) e DNS local (`dns`, 5300);
  2. a cada ciclo (`report_interval`): verifica usuário ativo, contata o servidor
     (`health`), baixa listas (`fetch_lists`), grava cache em
     `/run/gltd-kid-control/lists_cache.json`, atualiza domínios do DNS,
     bloqueia navegadores (`enforce`), aplica redirect DNS, coleta uso/histórico
     e reporta (`reporter`), envia heartbeat.
- **`enforce.py`** — `active_user()` (via `loginctl`/`who`), `kill_forbidden_browsers()`
  (mata processos de navegadores não autorizados do usuário), `apply_dns_redirect()`
  (iptables `REDIRECT --uid-owner` para a porta 5300).
- **`dns.py`** — `LocalDNS` (UDP+TCP em `127.0.0.1:5300`): responde `NXDOMAIN`
  para domínios bloqueados e encaminha o restante ao upstream (`/etc/resolv.conf`).
- **`localserver.py`** — HTTP local `127.0.0.1:8877` para a extensão:
  `GET /lists`, `GET /blocked`, `GET /health`, `GET /status`, `POST /pause`,
  `POST /resume`, `POST /report`.
- **`brave_history.py`** — lê o histórico do Brave (SQLite read-only), filtra
  vídeos do YouTube e enriquece via oEmbed.
- **`reporter.py`** — comunicação HTTP com o servidor (stdlib `urllib`).
- **`tray.py`** — ícone de status (AppIndicator/GTK3), somente informativo.

### Arquivos de runtime (cliente)

- `/etc/gltd-kid-control/client.json` — config (root-only, `0600`).
- `/run/gltd-kid-control/{status.json, lists_cache.json, admin_hash,
  paused.json, blocked_attempts.jsonl}`.
- `/var/lib/gltd-kid-control/client_state.json` — cursor do histórico do Brave.

---

## 9. Dados sensíveis e `.gitignore` (LEIA)

**Nunca** envie ao repositório:

- `data/` — logs, histórico (SQLite), pid.
- `config/server.json` — senha/hash do admin e senha do banco.
- `client/keys/` e qualquer `*.pem`/`*.key` — chave privada da extensão.
- `**/dist/`, `*.deb`, `*.crx` — artefatos de build.
- `/lists/block_manual_*.csv` — bloqueios manuais gerados em runtime.
- `/vendor/` — PyMySQL vendored (instalar via apt/pip).
- `__pycache__/`, `*.pyc`.

Ao editar o projeto, **não** adicione nomes reais de crianças, IPs internos
específicos, credenciais ou qualquer dado pessoal. Use os exemplos genéricos já
presentes (`child1`, `child2`, `192.168.1.100`, `servidor.local`).

---

## 10. Convenções de código

- Python 3.10+; HTTP com stdlib; dados via `pymysql` (ou JSON fallback).
- Nomes de pacote/módulo em `snake_case`.
- Dataclasses em `models.py`; persistência via `db.py` (sem ORM).
- Mensagens de UI em português do Brasil.
- Não adicionar comentários óbvios; comentar apenas "porquês" não triviais.
- Evitar dependências externas no runtime (stdlib primeiro).

---

## 11. Comandos úteis

```bash
# servidor em modo dev
python3 -m gltd_kid_server --config config/server.example.json --port 8123

# validar listas CSV (passa o diretório como argumento)
python3 -m gltd_kid_server.lists ../lists

# build dos pacotes
bash server/scripts/build_deb.sh
bash client/scripts/build_deb.sh

# extensão (CRX)
python3 client/scripts/make_crx.py client/extension client/extension/gltd.crx client/keys/gltd_ext_key.pem
```
