from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
import pdfkit
from datetime import datetime
#from flask_weasyprint import HTML
#from weasyprint import HTML


app = Flask(__name__)
app.secret_key = "sua_chave_secreta"  # Necessária para gerenciar a sessão

# Banco de dados SQLite
DB_FILE = "julio_tech.db"

# Função para conectar ao banco de dados
def conectar_bd():
    return sqlite3.connect(DB_FILE)


# Função para criar as tabelas no banco de dados (se não existirem)
def criar_tabelas():
    conn = conectar_bd()
    cursor = conn.cursor()

    # Criação da tabela de clientes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            endereco TEXT
        )
    """)

    # Criação da tabela de estoque
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            preco REAL NOT NULL
        )
    """)

    # Criação da tabela de serviços
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            data_servico TEXT NOT NULL,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    """)
    
    # Criação da tabela de usuários
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL
        )
    """)

    # Criação da tabela de relação entre serviços e itens do estoque
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS servicos_estoque (
    servico_id INTEGER,
    estoque_id INTEGER,
    quantidade_usada INTEGER,
    FOREIGN KEY (servico_id) REFERENCES servicos(id),
    FOREIGN KEY (estoque_id) REFERENCES estoque(id)
);

""")


    # Verificar se o usuário "admin" existe e, caso não, criar
    cursor.execute("SELECT * FROM usuarios WHERE usuario = 'admin'")
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO usuarios (usuario, senha) VALUES (?, ?)", ("admin", "1234"))
        conn.commit()

    conn.commit()
    conn.close()
    print("Banco de dados e usuário inicial 'admin' criados com sucesso!")

# Rota de login
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        # Verificar no banco de dados
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE usuario = ? AND senha = ?", (usuario, senha))
        user = cursor.fetchone()
        conn.close()

        if user:
            session["usuario"] = usuario  # Salva o usuário na sessão
            return redirect(url_for("dashboard"))
        else:
            return "Usuário ou senha inválidos!", 403
    return render_template("index.html")

############ Rota para Dasnboard
@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:  # Verifica se o usuário está autenticado
        return redirect(url_for("login"))

    # Conectar ao banco de dados
    conn = conectar_bd()
    cursor = conn.cursor()

    # Recuperar os clientes cadastrados (últimos 5)
    cursor.execute("SELECT * FROM clientes ORDER BY id DESC LIMIT 5")
    clientes = cursor.fetchall()

    # Recuperar os serviços realizados (últimos 5)
    cursor.execute("SELECT * FROM servicos ORDER BY id DESC LIMIT 5")
    servicos = cursor.fetchall()

    # Somar a quantidade total de itens em estoque
    cursor.execute("SELECT SUM(quantidade) FROM estoque")
    total_estoque = cursor.fetchone()[0]  # Soma de todas as quantidades dos itens no estoque

    # Recuperar o total de receita
    cursor.execute("SELECT SUM(valor) FROM servicos")
    receita_total = cursor.fetchone()[0] or 0  # Evitar erro se não houver serviços

    # Contar total de clientes
    cursor.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = cursor.fetchone()[0]

    # Contar total de serviços
    cursor.execute("SELECT COUNT(*) FROM servicos")
    total_servicos = cursor.fetchone()[0]

    conn.close()

    # Renderizar a página com os dados do Dashboard
    return render_template("dashboard.html",
                           usuario=session["usuario"],
                           total_clientes=total_clientes,  # Contagem de clientes
                           total_servicos=total_servicos,  # Contagem de serviços
                           total_estoque=total_estoque,    # Quantidade total de itens no estoque
                           receita_total=receita_total,    # Total de receita
                           clientes=clientes,  # Passa os últimos 5 clientes
                           servicos=servicos)  # Passa os últimos 5 serviços




############### Rota para logout
@app.route("/logout")
def logout():
    session.pop("usuario", None)  # Remove o usuário da sessão
    return redirect(url_for("index"))

############### Rota para gerenciar clientes
@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    if "usuario" not in session:
        return redirect(url_for("index"))

    # Obter o termo de busca, se houver
    busca = request.args.get("busca", "")
    pagina = int(request.args.get("pagina", 1))
    registros_por_pagina = 10
    offset = (pagina - 1) * registros_por_pagina

    # Conectar ao banco de dados
    conn = conectar_bd()
    cursor = conn.cursor()

    # Buscar clientes com base no termo de busca
    if busca:
        cursor.execute("""
            SELECT * FROM clientes WHERE nome LIKE ? OR telefone LIKE ? OR endereco LIKE ?
            LIMIT ? OFFSET ?
        """, (f"%{busca}%", f"%{busca}%", f"%{busca}%", registros_por_pagina, offset))
    else:
        cursor.execute("""
            SELECT * FROM clientes LIMIT ? OFFSET ?
        """, (registros_por_pagina, offset))

    clientes = cursor.fetchall()

    # Contar o total de clientes (para a navegação da paginação)
    if busca:
        cursor.execute("""
            SELECT COUNT(*) FROM clientes WHERE nome LIKE ? OR telefone LIKE ? OR endereco LIKE ?
        """, (f"%{busca}%", f"%{busca}%", f"%{busca}%"))
    else:
        cursor.execute("SELECT COUNT(*) FROM clientes")
    
    total_clientes = cursor.fetchone()[0]

    conn.close()

    # Calcular o número total de páginas
    total_paginas = (total_clientes + registros_por_pagina - 1) // registros_por_pagina

    return render_template(
        "clientes.html",
        clientes=clientes,
        pagina=pagina,
        total_paginas=total_paginas,
        busca=busca  # Passa o termo de busca para o template
    )


#################Rota para gerenciar serviços
@app.route("/servicos", methods=["GET"])
def servicos():
    if "usuario" not in session:
        return redirect(url_for("index"))

    # Conectar ao banco de dados
    conn = conectar_bd()
    cursor = conn.cursor()

    # Parâmetros de busca e paginação
    busca = request.args.get("busca", "").strip()
    pagina = int(request.args.get("pagina", 1))  # Página atual (default: 1)
    por_pagina = 5  # Número de serviços por página
    offset = (pagina - 1) * por_pagina

    # Contar total de serviços (com ou sem busca)
    if busca:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM servicos 
            JOIN clientes ON servicos.cliente_id = clientes.id 
            WHERE clientes.nome LIKE ? OR servicos.descricao LIKE ?
        """, (f"%{busca}%", f"%{busca}%"))
    else:
        cursor.execute("SELECT COUNT(*) FROM servicos")
    
    total_servicos = cursor.fetchone()[0]
    total_paginas = (total_servicos + por_pagina - 1) // por_pagina  # Calcular o total de páginas

    # Consultar os serviços com paginação
    if busca:
        cursor.execute("""
            SELECT servicos.id, clientes.nome, servicos.descricao, servicos.valor
            FROM servicos 
            JOIN clientes ON servicos.cliente_id = clientes.id 
            WHERE clientes.nome LIKE ? OR servicos.descricao LIKE ? 
            ORDER BY servicos.id DESC 
            LIMIT ? OFFSET ?
        """, (f"%{busca}%", f"%{busca}%", por_pagina, offset))
    else:
        cursor.execute("""
            SELECT servicos.id, clientes.nome, servicos.descricao, servicos.valor 
            FROM servicos 
            JOIN clientes ON servicos.cliente_id = clientes.id 
            ORDER BY servicos.id DESC 
            LIMIT ? OFFSET ?
        """, (por_pagina, offset))
    
    servicos = cursor.fetchall()

    # Fechar conexão
    conn.close()

    return render_template(
        "servicos.html",
        servicos=servicos,
        busca=busca,
        pagina=pagina,
        total_paginas=total_paginas
    )

######### Rota para Detalhes do serviço
@app.route("/servicos/<int:id>", methods=["GET"])
def detalhes_servico(id):
    if "usuario" not in session:
        return redirect(url_for("index"))
    
    # Conectar ao banco de dados
    conn = conectar_bd()
    cursor = conn.cursor()

    # Buscar informações detalhadas do serviço
    cursor.execute("""
        SELECT servicos.id, clientes.nome, servicos.descricao, servicos.valor
        FROM servicos
        JOIN clientes ON servicos.cliente_id = clientes.id 
        WHERE servicos.id = ?
    """, (id,))
    servico = cursor.fetchone()

    # Fechar a conexão
    conn.close()

    if servico:
        return render_template("detalhes_servico.html", servico=servico)
    else:
        return "Serviço não encontrado", 404



#################Rota para editar serviços
@app.route("/servicos/editar/<int:servico_id>", methods=["GET", "POST"])
def editar_servico(servico_id):
    if "usuario" not in session:
        return redirect(url_for("index"))

    conn = conectar_bd()
    cursor = conn.cursor()

    # Buscar os dados do serviço e cliente
    cursor.execute("""
        SELECT s.id, s.descricao, s.valor, s.data_servico, c.id, c.nome
        FROM servicos AS s
        JOIN clientes AS c ON s.cliente_id = c.id
        WHERE s.id = ?
    """, (servico_id,))
    servico = cursor.fetchone()

    # Buscar os itens de estoque usados no serviço
    cursor.execute("""
        SELECT e.id, e.nome, se.quantidade_usada
        FROM servicos_estoque AS se
        JOIN estoque AS e ON se.estoque_id = e.id
        WHERE se.servico_id = ?
    """, (servico_id,))
    itens_estoque = cursor.fetchall()

    # Buscar todos os clientes para a seleção
    cursor.execute("SELECT id, nome FROM clientes")
    clientes = cursor.fetchall()

    conn.close()

    if not servico:
        return "Serviço não encontrado.", 404

    # Se o método for POST, atualizar o serviço e os itens de estoque
    if request.method == "POST":
        descricao = request.form["descricao"]
        valor = request.form["valor"]
        cliente_id = request.form["cliente_id"]

        conn = conectar_bd()
        cursor = conn.cursor()

        # Atualizar o serviço
        cursor.execute("""
            UPDATE servicos
            SET descricao = ?, valor = ?, cliente_id = ?
            WHERE id = ?
        """, (descricao, valor, cliente_id, servico_id))

        # Atualizar os itens do estoque (remover itens anteriores e adicionar novos)
        cursor.execute("DELETE FROM servicos_estoque WHERE servico_id = ?", (servico_id,))
        itens = request.form.getlist("itens_estoque")  # IDs dos itens selecionados
        quantidades = request.form.getlist("quantidade")  # Quantidades editadas

        for item_id, quantidade in zip(itens, quantidades):
            quantidade = int(quantidade)

            # Atualizar a tabela servicos_estoque com os novos valores
            cursor.execute("""
                INSERT INTO servicos_estoque (servico_id, estoque_id, quantidade_usada)
                VALUES (?, ?, ?)
            """, (servico_id, item_id, quantidade))

        conn.commit()
        conn.close()

        return redirect(url_for("servicos"))

    return render_template("editar_servico.html", servico=servico, itens_estoque=itens_estoque, clientes=clientes)

###### Rota para Ordem de serviço OS
@app.route("/servicos/os/<int:servico_id>", methods=["GET", "POST"])
def ordem_servico(servico_id):
    if "usuario" not in session:
        return redirect(url_for("login"))

    conn = conectar_bd()
    cursor = conn.cursor()

    # Buscar os dados do serviço e cliente
    cursor.execute("""
        SELECT s.id, s.descricao, s.valor, s.data_servico, c.nome, c.telefone, c.endereco
        FROM servicos AS s
        JOIN clientes AS c ON s.cliente_id = c.id
        WHERE s.id = ?
    """, (servico_id,))
    servico = cursor.fetchone()

    # Buscar itens do estoque relacionados ao serviço
    cursor.execute("""
        SELECT e.nome, se.quantidade_usada
        FROM servicos_estoque AS se
        JOIN estoque AS e ON se.estoque_id = e.id
        WHERE se.servico_id = ?
    """, (servico_id,))
    itens = cursor.fetchall()

    conn.close()

    if not servico:
        return "Serviço não encontrado.", 404

    # Número da OS
    numero_os = f"OS-{servico_id:06d}"  # Formato OS-000001, por exemplo.

    return render_template("os.html", servico=servico, itens=itens, numero_os=numero_os)

#########Rota para visualizar OS
@app.route("/servicos/os/<int:servico_id>")
def visualizar_os(servico_id):
    # Busque os dados do serviço, cliente, itens do estoque
    conn = conectar_bd()
    cursor = conn.cursor()
    # ... (dados do serviço e cliente como já fizemos)
    return render_template("ordem_servico.html", servico=servico, itens=itens)



#################Rota para excluir serviços
@app.route("/servicos/excluir/<int:id>", methods=["GET"])
def excluir_servico(id):
    if "usuario" not in session:
        return redirect(url_for("index"))

    # Conectar ao banco de dados e excluir o serviço
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM servicos WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("servicos"))


#################Rota para gerar relatórios
@app.route("/relatorios")
def relatorios():
    if "usuario" not in session:
        return redirect(url_for("index"))
    return "Página de Relatórios (em desenvolvimento)"

@app.route("/clientes/novo", methods=["GET", "POST"])
def adicionar_cliente():
    if "usuario" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        nome = request.form["nome"]
        telefone = request.form["telefone"]
        endereco = request.form["endereco"]

        conn = conectar_bd()
        cursor = conn.cursor()

        # Inserir o cliente no banco de dados
        cursor.execute("""
            INSERT INTO clientes (nome, telefone, endereco)
            VALUES (?, ?, ?)
        """, (nome, telefone, endereco))

        conn.commit()
        conn.close()

        return redirect(url_for("clientes"))

    # Se for GET, exibe o formulário para adicionar cliente
    return render_template("adicionar_cliente.html")


    
        
###############Rota para adicionar um novo serviço
@app.route("/servicos/novo", methods=["GET", "POST"])
def adicionar_servico():
    if "usuario" not in session:
        return redirect(url_for("index"))

    conn = conectar_bd()
    cursor = conn.cursor()

    if request.method == "POST":
        # Recuperar os dados do formulário
        cliente_id = request.form["cliente_id"]
        descricao = request.form["descricao"]
        valor = request.form["valor"]
        incluir_estoque = request.form.get("incluir_estoque")  # Checkbox para verificar uso de estoque

        # Inserir o serviço no banco de dados
        cursor.execute("""
            INSERT INTO servicos (cliente_id, descricao, valor, data_servico)
            VALUES (?, ?, ?, date('now'))
        """, (cliente_id, descricao, valor))
        servico_id = cursor.lastrowid

        # Se incluir_estoque está marcado, processar os itens do estoque
        if incluir_estoque:
            itens = request.form.getlist("itens_estoque")  # IDs dos itens selecionados
            quantidades = request.form.getlist("quantidade")  # Quantidades utilizadas

            for item_id, quantidade in zip(itens, quantidades):
                quantidade = int(quantidade)
                if quantidade > 0:
                    # Atualizar a quantidade no estoque e prevenir estoque negativo
                    cursor.execute("""
                        UPDATE estoque 
                        SET quantidade = quantidade - ? 
                        WHERE id = ? AND quantidade >= ?
                    """, (quantidade, item_id, quantidade))

                    # Registrar a relação entre o serviço e o item
                    cursor.execute("""
                        INSERT INTO servicos_estoque (servico_id, estoque_id, quantidade_usada)
                        VALUES (?, ?, ?)
                    """, (servico_id, item_id, quantidade))

        conn.commit()
        conn.close()
        return redirect(url_for("servicos"))

    # Recuperar dados para o formulário
    cursor.execute("SELECT id, nome FROM clientes")
    clientes = cursor.fetchall()

    cursor.execute("SELECT id, nome, quantidade FROM estoque WHERE quantidade > 0")
    itens_estoque = cursor.fetchall()

    conn.close()
    return render_template("adicionar_servico.html", clientes=clientes, itens_estoque=itens_estoque)


######################## Rota busca de item no estoque
@app.route("/api/estoque")
def api_estoque():
    query = request.args.get("query", "").lower()

    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, quantidade FROM estoque WHERE LOWER(nome) LIKE ? AND quantidade > 0", (f"%{query}%",))
    itens = [{"id": row[0], "nome": row[1], "quantidade": row[2]} for row in cursor.fetchall()]
    conn.close()

    return jsonify(itens)


######################## Rota para editar um cliente
@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    if "usuario" not in session:
        return redirect(url_for("index"))

    # Conectar ao banco de dados e buscar os dados do cliente
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes WHERE id = ?", (id,))
    cliente = cursor.fetchone()
    conn.close()

    if not cliente:
        return "Cliente não encontrado", 404

    # Se o formulário for enviado via POST, atualiza o cliente
    if request.method == "POST":
        nome = request.form["nome"]
        telefone = request.form["telefone"]
        endereco = request.form["endereco"]

        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE clientes
            SET nome = ?, telefone = ?, endereco = ?
            WHERE id = ?
        """, (nome, telefone, endereco, id))
        conn.commit()
        conn.close()

        return redirect(url_for("clientes"))

    return render_template("editar_cliente.html", cliente=cliente)

################# Rota para excluir um cliente
@app.route("/clientes/excluir/<int:id>", methods=["POST"])
def excluir_cliente(id):
    if "usuario" not in session:
        return redirect(url_for("index"))

    # Conectar ao banco de dados e excluir o cliente
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clientes WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("clientes"))


############### Rota para gerenciar estoque
@app.route('/estoque')
def exibir_estoque():
    # Parâmetros de busca e paginação
    busca = request.args.get('busca', '').strip()
    pagina = int(request.args.get('pagina', 1))
    itens_por_pagina = 10
    offset = (pagina - 1) * itens_por_pagina

    conn = sqlite3.connect('julio_tech.db')
    cursor = conn.cursor()

    # Consulta com busca e paginação
    if busca:
        cursor.execute("""
            SELECT id, nome, quantidade, preco FROM estoque
            WHERE nome LIKE ? 
            LIMIT ? OFFSET ?
        """, (f"%{busca}%", itens_por_pagina, offset))
    else:
        cursor.execute("""
            SELECT id, nome, quantidade, preco FROM estoque
            LIMIT ? OFFSET ?
        """, (itens_por_pagina, offset))

    itens = cursor.fetchall()

    # Contar total de itens (para paginação)
    if busca:
        cursor.execute("SELECT COUNT(*) FROM estoque WHERE nome LIKE ?", (f"%{busca}%",))
    else:
        cursor.execute("SELECT COUNT(*) FROM estoque")
    total_itens = cursor.fetchone()[0]
    total_paginas = -(-total_itens // itens_por_pagina)  # Arredondamento para cima

    conn.close()

    # Preparar dados para o template
    estoque = [{"id": i[0], "nome": i[1], "quantidade": i[2], "preco": i[3]} for i in itens]
    return render_template('estoque.html', estoque=estoque, busca=busca, pagina=pagina, total_paginas=total_paginas)

@app.route("/estoque/novo", methods=["GET", "POST"])
def adicionar_estoque():
    if "usuario" not in session:
        return redirect(url_for("index"))
    
    if request.method == "POST":
        # Lógica para adicionar o item ao banco de dados
        nome = request.form["nome"]
        quantidade = int(request.form["quantidade"])
        preco = float(request.form["preco"])
        
        conn = conectar_bd()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO estoque (nome, quantidade, preco) 
            VALUES (?, ?, ?)
        """, (nome, quantidade, preco))
        conn.commit()
        conn.close()

        return redirect(url_for("exibir_estoque"))  # Redireciona para a página principal do estoque
    
    return render_template("adicionar_estoque.html")  # Renderiza o HTML para adicionar itens

#################Rota para editar estoque
@app.route("/estoque/editar/<int:id>", methods=["GET", "POST"])
def editar_estoque(id):
    if "usuario" not in session:
        return redirect(url_for("index"))

    conn = conectar_bd()
    cursor = conn.cursor()

    if request.method == "POST":
        # Capturar os valores do formulário apenas no método POST
        nome = request.form.get("nome", "").strip()  # Remove espaços em branco
        quantidade = request.form.get("quantidade", "").strip()
        preco = request.form.get("preco", "").strip()

        print(url_for("exibir_estoque"))


        # Adicionar o print para depuração
        print("Valores recebidos do formulário:", nome, quantidade, preco)

        # Verifique se os valores obrigatórios não estão vazios
        if not nome:
            return "O campo 'nome' não pode estar vazio.", 400

        if not quantidade or not preco:
            return "Por favor, preencha todos os campos obrigatórios.", 400

        # Atualizar o item no banco de dados
        cursor.execute("""
            UPDATE estoque
            SET nome = ?, quantidade = ?, preco = ?
            WHERE id = ?
        """, (nome, quantidade, preco, id))
        conn.commit()
        conn.close()
        return redirect(url_for("exibir_estoque"))

    # Buscar dados do item a ser editado apenas no método GET
    cursor.execute("SELECT * FROM estoque WHERE id = ?", (id,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        return "Item não encontrado", 404

    # Renderizar o template com os dados do item
    return render_template("editar_estoque.html", item=item)



#################Rota para excluir item do estoque    
@app.route("/estoque/excluir/<int:id>", methods=["POST"])
def excluir_estoque(id):
    if "usuario" not in session:
        return redirect(url_for("index"))

    conn = conectar_bd()
    cursor = conn.cursor()

    # Exclui o item do banco de dados
    cursor.execute("DELETE FROM estoque WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("exibir_estoque"))







########## Rota de Recibo
from datetime import datetime

########## Rota de Recibo
@app.route("/servicos/recibo/<int:servico_id>", methods=["GET", "POST"])
def gerar_recibo(servico_id):
    if "usuario" not in session:
        return redirect(url_for("index"))

    conn = conectar_bd()
    cursor = conn.cursor()

    # Buscar os dados do serviço e cliente
    cursor.execute("""
        SELECT s.id, s.descricao, s.valor, s.data_servico, c.nome, c.telefone, c.endereco
        FROM servicos AS s
        JOIN clientes AS c ON s.cliente_id = c.id
        WHERE s.id = ?
    """, (servico_id,))
    servico = cursor.fetchone()

    if not servico:
        return "Serviço não encontrado.", 404

    # Reformatar a data para o formato DD/MM/YYYY
    try:
        data_formatada = datetime.strptime(servico[3], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        data_formatada = servico[3]  # Mantém o formato original em caso de erro

    # Atualizar a tupla `servico` com a data formatada
    servico = (servico[0], servico[1], servico[2], data_formatada, servico[4], servico[5], servico[6])

    # Buscar itens do estoque relacionados ao serviço
    cursor.execute("""
        SELECT e.id, e.nome, se.quantidade_usada
        FROM servicos_estoque AS se
        JOIN estoque AS e ON se.estoque_id = e.id
        WHERE se.servico_id = ?
    """, (servico_id,))
    itens = cursor.fetchall()

    conn.close()

    return render_template("recibo.html", servico=servico, itens=itens)




if __name__ == "__main__":
    criar_tabelas()  # Garantir que as tabelas sejam criadas
    app.run(debug=True)
