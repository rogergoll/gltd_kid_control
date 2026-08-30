# HOWTO — Instalação e configuração

Este documento descreve como instalar e configurar o **GLTD Kid Control** em
um ambiente Debian/Linux Mint. A instalação é dividida em duas partes: o
**servidor** (painel do responsável) e o **cliente** (máquina da criança).

> **Aviso:** projeto em fase inicial, de uso pessoal. Use por sua conta e risco.

---

## 1. Visão geral

```
                    +--------------------------+
                    |  SERVER (máquina do pai) |
                    |  gltd-kid-server (8123)  |
                    |  MariaDB / JSON          |
                    |  DNS local (5300)        |
                    +------------+-------------+
                                 | LAN
              +------------------+------------------+
              |                                     |
     +--------v--------+                 +----------v--------+
     | CLIENT (criança)|                 | CLIENT (criança)  |
     | gltd-kid-client |                 | gltd-kid-client   |
     | Brave + extensão|                 | Brave + extensão  |
     +-----------------+                 +-------------------+
```

- O **servidor** guarda os perfis, as listas de canais bloqueados/recomendados
  (CSV) e o histórico de visualizações. Expõe uma API HTTP JSON e um painel web.
- O **cliente** roda como daemon (root) na máquina da criança, bloqueia
  navegadores não autorizados, redireciona o DNS e reporta uso/histórico.

---

## 2. Pré-requisitos

### Servidor
- Linux baseado em Debian (recomendado **Linux Mint**).
- Python 3.10 ou superior.
- (recomendado) MariaDB Server e o driver Python `pymysql`.
- `curl`, `git` (para instalação manual a partir do repositório).

### Cliente
- Linux Mint com o navegador **Brave** instalado.
- `libnotify-bin` (para as notificações do ícone de status).

---

## 3. Instalar o servidor

### 3.1. Dependências

```bash
sudo apt update
sudo apt install -y python3 python3-pymysql mariadb-server mariadb-client curl
```

> Se preferir **não** usar MariaDB, o servidor pode operar com o backend
> **JSON** (arquivos no diretório de dados). Nesse caso o `python3-pymysql` e o
> MariaDB são opcionais.

### 3.2. Obter o código

```bash
git clone git@github.com:rogergoll/gltd_kid_control.git
cd gltd_kid_control
```

### 3.3. Configurar o banco de dados (MariaDB)

```bash
sudo mysql <<'SQL'
CREATE DATABASE IF NOT EXISTS gltd_kcontrol CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER IF NOT EXISTS 'gltd_kcontrol_app'@'localhost' IDENTIFIED BY 'SUA_SENHA_FORTE';
GRANT ALL PRIVILEGES ON gltd_kcontrol.* TO 'gltd_kcontrol_app'@'localhost';
FLUSH PRIVILEGES;
SQL
```

O esquema (tabelas) é criado automaticamente pelo servidor na primeira execução.
O arquivo `server/sql/schema.sql` contém o schema para referência.

### 3.4. Criar o arquivo de configuração

Copie o exemplo e ajuste:

```bash
cp config/server.example.json /etc/gltd-kid-control/config.json
```

Edite `/etc/gltd-kid-control/config.json`. Campos importantes:

| campo | descrição |
|---|---|
| `listen_host` / `listen_port` | endereço/porta HTTP do painel (padrão `8123`) |
| `data_dir` | diretório de dados (JSON/histórico) |
| `lists_dir` | diretório das listas CSV |
| `db_backend` | `"mariadb"` ou `"json"` |
| `db_host` / `db_port` / `db_user` / `db_password` / `db_name` | credenciais do MariaDB |
| `profiles` | perfis das crianças (id, lan_ip, linux_user, listas, navegadores) |

Exemplo de perfil:

```json
{
  "id": "child1",
  "name": "Crianca 1",
  "lan_ip": "192.168.1.100",
  "linux_user": "child1",
  "allowed_browsers": ["brave-browser"],
  "block_lists": ["block_child1.csv", "block_baixa_cultura.csv"],
  "allow_lists": ["allow_child1.csv"],
  "filters": []
}
```

> **Importante:** não versionar/configurar senhas reais em arquivos públicos.
> O arquivo real (`config/server.json`) é ignorado pelo git.

### 3.5. Executar o servidor

Instalação manual (modo desenvolvimento):

```bash
bash server/scripts/install.sh
```

Ou rode diretamente em modo de desenvolvimento:

```bash
cd server
python3 -m gltd_kid_server --config /etc/gltd-kid-control/config.json
```

Para subir em segundo plano (e abrir o painel):

```bash
bash server/scripts/server_start.sh      # sobe o servidor
bash server/scripts/start_admin.sh       # sobe + abre o painel no navegador
bash server/scripts/server_stop.sh       # encerra o servidor
```

Acesse o painel em **http://localhost:8123**. Na primeira execução, o assistente
de configuração (`/setup`) pede o usuário e a senha do administrador.

---

## 4. Instalar o cliente (na máquina da criança)

### 4.1. Gerar o pacote `.deb`

Na pasta do repositório:

```bash
bash client/scripts/build_deb.sh
```

O pacote é gerado em `client/dist/gltd-kid-control-client_0.1.0_all.deb`.

### 4.2. Instalar e configurar

```bash
sudo dpkg -i gltd-kid-control-client_0.1.0_all.deb
sudo gltd-kid-client setup
```

O `setup` pergunta:

1. **URL do servidor** (ex.: `http://192.168.1.100:8123`).
2. **ID do perfil** (definido no painel do servidor).
3. **Token do client** (copiado do painel do servidor).
4. **Usuário Linux** da criança afetado pelo perfil.

A configuração é gravada em `/etc/gltd-kid-control/client.json` (root-only) e o
daemon é iniciado/gerenciado pelo systemd (`gltd-kid-client.service`).

---

## 5. Extensão do navegador (YouTube)

A extensão do Brave/Chrome remodela o YouTube (remove Shorts e recomendações) e
bloqueia canais/vídeos. Ela é empacotada junto com o `.deb` do cliente e
instalada automaticamente como "external extension".

Para gerar o pacote `.crx` manualmente:

```bash
python3 client/scripts/make_crx.py client/extension client/extension/gltd.crx client/keys/gltd_ext_key.pem
```

> **Guarde a chave privada** (`client/keys/gltd_ext_key.pem`). Ela é necessária
> para assinar novas versões da extensão. Nunca a envie ao repositório.

---

## 6. DNS local (bloqueio de domínios)

O servidor pode rodar um DNS local que responde `NXDOMAIN` para domínios
bloqueados e encaminha o restante ao DNS padrão:

```bash
bash server/scripts/dns_start.sh 5300
```

O cliente redireciona as consultas DNS do usuário-criança para esse servidor
via `iptables` (regra `REDIRECT` por `--uid-owner`).

---

## 7. Testes manuais

```bash
# Servidor
curl http://localhost:8123/api/health

# Cliente
gltd-kid-client status     # mostra o status atual
gltd-kid-client once       # executa um ciclo (enforce + report)
gltd-kid-client daemon     # roda o daemon em primeiro plano (debug)
```

---

## 8. Solução de problemas

| sintoma | causa provável / solução |
|---|---|
| `Address already in use` na porta 8123 | já existe um servidor rodando; use `server/scripts/server_stop.sh` |
| cliente não conecta | verifique `server_url`, `client_token` e se o servidor escuta em `0.0.0.0` |
| histórico não aparece | confirme que o backend de dados (MariaDB/JSON) está acessível |
| extensão não instala | confirme o `.crx` e a pasta `/opt/brave.com/brave/extensions` |

Logs: `data/server.log`, `data/dns.log` (no diretório do repositório).
