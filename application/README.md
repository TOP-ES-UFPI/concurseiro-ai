# Concurseiro AI

## Como iniciar o projeto

1.  **Navegue até a pasta `application`:**

    ```bash
    cd application
    ```

2.  **Crie um ambiente virtual:**

    ```bash
    python -m venv venv
    ```

3.  **Ative o ambiente virtual:**

    *   No Linux ou macOS:
        ```bash
        source venv/bin/activate
        ```
    *   No Windows:
        ```bash
        venv\Scripts\activate
        ```

4.  **Instale as dependências:**

    ```bash
    pip install -r requirements.txt
    ```

5.  **Execute as migrações:**

    ```bash
    python manage.py migrate
    ```

6.  **Inicie o servidor de desenvolvimento:**

    ```bash
    python manage.py runserver
    ```

O projeto estará rodando em `http://127.0.0.1:8000/`.

## Como criar um superusuário

Para criar um superusuário, execute o comando abaixo e siga as instruções:

```bash
python manage.py createsuperuser
```