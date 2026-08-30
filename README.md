# GLTD Kid Control

Controle parental livre, para a sua casa e para a sua LAN.

Um sistema composto por um **servidor** (painel do responsável) e **clientes**
(as máquinas usadas pelas crianças). O servidor define perfis e listas de
conteúdo permitido/bloqueado; o cliente altera a forma como a máquina interage
com DNS, bloqueia navegadores não autorizados e reporta uso de aplicativos e
histórico ao servidor — tudo dentro da sua rede, sem depender de nenhum serviço
externo.

---

## Por que este projeto existe

Sou pai e tenho dois filhos. A internet não é mais a mesma de quando tudo
começou.

No início, a internet era feita por pessoas e para pessoas, baseada em pesquisa
e interação. Não era voltada ao consumo e ao vício.

Hoje, as redes sociais no ocidente são direcionadas apenas a extrair o máximo de
tela do usuário. Os algoritmos, em vez de induzirem a evolução do usuário,
tendem sempre a puxar para baixo o nível intelectual. Isso pode ser fatal para
crianças. Eu mesmo luto para evitar comportamentos compulsivos no uso de redes
sociais e o excesso de informação.

Este projeto nasceu da minha insatisfação com o que eu via e com os recursos de
controle parental disponíveis.

Também sou contra o formato como a classificação de conteúdo para crianças é
feita. Cabe aos pais definir isso — essa responsabilidade é dos pais, e não de
um governo ou de uma big tech.

## Como é feito

- **Este projeto é feito todo usando IA** (DeepSeek). A qualidade do código pode
  ser questionável.
- Funciona inicialmente como um **gestor de conteúdo em uma LAN**, para uso
  doméstico.
- É otimizado para **Debian/Linux Mint**. Em breve: outras opções, além de uma
  versão de gestor e de cliente para **Android**.

## Avisos importantes

- O uso inicial é **pessoal**. Não posso garantir a segurança da aplicação.
  **Use por sua conta e risco.**
- **Não extraímos nem coletamos nenhuma informação sua.** A aplicação não depende
  de um servidor meu ou de qualquer outra empresa para funcionar — tudo roda na
  sua própria rede.

## Requisitos de ambiente

- **Servidor:** Linux baseado em Debian (recomendado Linux Mint), Python 3.10+.
  Banco de dados MariaDB (recomendado) ou JSON local.
- **Cliente:** Linux Mint com navegador Brave (as máquinas das crianças).
- Rede local (LAN) entre servidor e clientes.

Veja a instalação passo a passo em **[HOWTO.md](HOWTO.md)**.

## Instalação (resumo)

```bash
# Servidor
sudo apt install python3 mariadb-server mariadb-client python3-pymysql
bash server/scripts/install.sh
sudo gltd-kid-server --config /etc/gltd-kid-control/config.json

# Cliente (na máquina da criança)
sudo dpkg -i gltd-kid-control-client_0.1.0_all.deb
sudo gltd-kid-client setup
```

Detalhes completos em **[HOWTO.md](HOWTO.md)**.

## Documentação

- **[HOWTO.md](HOWTO.md)** — instalação e configuração.
- **[README_AGENT.MD](README_AGENT.MD)** — documentação técnica (para
  desenvolvedores e agentes de IA).

---

## Apoie o projeto

Este projeto é feito no meu tempo livre, com os tokens e recursos que disponho.
Se você quiser contribuir financeiramente, agradeço!

Também fico grato se divulgar esta aplicação. Meu X: [@rogergoll](https://x.com/rogergoll)

- **XMR (Monero):**
  `88oYWeR7ZEVXUnAuZRXbYaWwowtcq6jZoMkNpC9VNukd1MMoZmoCFodgcyVU6GuUjdGhf5R5G45ZNh9wV8jdyFPJ1APiVAG`
- **Dogecoin:** `DMUuoV6tvBfXyYbMpRjSM6pstuYFuC7Jfb`
- **Bitcoin:** `bc1q4lftxmqth33htrgjg3s4f5dzjr2d7gdw76wn4n`
- **Pix (Brasil):** `1f57a276-dc0e-44a0-a4e0-4a2349833958`

## Licença

[Apache License 2.0](LICENSE)
