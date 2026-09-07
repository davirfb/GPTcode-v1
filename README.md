# GPTCode - Grupo de Pesquisa em Tecnologias Computacionais

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3+-purple.svg)](https://getbootstrap.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Website oficial do **GPTCode** - Grupo de Pesquisa em Tecnologias Computacionais do Instituto Federal de Brasília (IFB).

## 📋 Índice

- [Sobre o Projeto](#sobre-o-projeto)
- [Características](#características)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Tecnologias Utilizadas](#tecnologias-utilizadas)
- [Instalação](#instalação)
- [Como Usar](#como-usar)
- [Estrutura de Páginas](#estrutura-de-páginas)
- [Personalizações e Boas Práticas](#personalizações-e-boas-práticas)
- [Responsividade](#responsividade)
- [Animações](#animações)
- [Performance](#performance)
- [Contribuição](#contribuição)
- [Licença](#licença)

---

## 🎯 Sobre o Projeto

O **GPTCode** é um grupo de pesquisa multidisciplinar do IFB dedicado ao desenvolvimento de **tecnologias computacionais inovadoras**. Este website apresenta:

- 📚 Informações sobre o grupo de pesquisa
- 🔬 Projetos em andamento (PIBIC, PIBITI, TCC)
- 📄 Publicações científicas
- 👥 Equipe de pesquisadores
- 💬 Formulário de contato
- 👨‍💻 Equipe de desenvolvedores
- 🤝 Parceiros e apoiadores

---

## ✨ Características

### 🎨 Design Moderno
- Interface limpa e intuitiva
- Tema de cores profissional (azul escuro com acentos dourados)
- Navbar responsiva com animações suaves
- Footer centrado com redes sociais

### 🚀 Performance Otimizada
- CSS consolidado e sem duplicação
- JavaScript refatorado (40% menos linhas de código)
- Lazy loading com IntersectionObserver
- Transições suaves com cubic-bezier easing

### 📱 Responsividade Completa
- 8 breakpoints diferentes (1920px → <380px)
- Otimizado para desktop, tablet e mobile
- Imagens responsivas
- Navegação adaptativa

### ✨ Animações Envolventes
- Fade-in suave ao carregar página (4.5s)
- Fade-in-up para cards
- Fade-in-down para títulos
- Fade-in-left/right para elementos laterais
- Sistema de delay e stagger para efeito cascata

### 🔒 Boas Práticas
- HTML semântico
- CSS modular e organizado
- JavaScript limpo e comentado
- Sem HTML duplicado
- Seguindo princípios DRY, KISS e SOLID

---

## 📁 Estrutura do Projeto

```
gptcode-site-ofc/
├── app.py                          # Aplicação Flask principal
├── requirements.txt                # Dependências Python
├── Procfile                        # Configuração para deploy
├── README.md                       # Este arquivo
├── REFACTORING.md                  # Documentação de refatoração
│
├── templates/                      # Templates HTML (Jinja2)
│   ├── base.html                   # Template base (estendido por todos)
│   ├── index.html                  # Página inicial
│   ├── projetos.html               # Página de projetos
│   ├── publicacoes.html            # Página de publicações
│   ├── equipe.html                 # Página da equipe
│   ├── contato.html                # Página de contato
│   └── devs.html                   # Página de desenvolvedores
│
├── static/                         # Arquivos estáticos
│   ├── css/                        # Estilos CSS
│   │   ├── main.css                # Estilos globais (1899 linhas)
│   │   ├── animacoes.css           # Sistema de animações (493 linhas)
│   │   ├── projetos.css            # Estilos para página de projetos
│   │   ├── equipe.css              # Estilos para página de equipe
│   │   ├── publicacoes.css         # Estilos para página de publicações
│   │   ├── pesquisas.css           # Estilos para página de pesquisas
│   │   └── contato.css             # Estilos para página de contato
│   │
│   ├── js/                         # Scripts JavaScript
│   │   └── main.js                 # Script principal (200 linhas)
│   │
│   └── imagens/                    # Imagens e logos
│       ├── logos/                  # Logos e ícones
│       │   ├── GPTCODE-LOGO-BARRA.png
│       │   ├── logo-removebg-preview.png
│       │   ├── gptcode-icon.png
│       │   ├── cnpq-icon.png
│       │   └── Instituto_Federal_de_Brasília.png
│       └── equipe/                 # Fotos da equipe
│           ├── alunos/
│           │   ├── graduacao/
│           │   └── ExAlunos do IFB e ou Colaboradores Externos/
│           └── professores/
```

---

## 🛠️ Tecnologias Utilizadas

### Backend
- **Python 3.8+** - Linguagem de programação
- **Flask 2.0+** - Framework web leve e poderoso
- **Jinja2** - Motor de templates

### Frontend
- **HTML5** - Estrutura semântica
- **CSS3** - Estilos com media queries e animações
- **JavaScript (ES6+)** - Interatividade
- **Bootstrap 5.3** - Framework CSS responsivo
- **Bootstrap Icons** - Conjunto de ícones

### Ferramentas e Bibliotecas
- **Google Fonts** - Tipografia (Poppins)
- **Cubic-bezier** - Easing functions para animações
- **IntersectionObserver API** - Lazy animation loading

---

## 📦 Instalação

### Pré-requisitos
- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)
- Git

### Passos de Instalação

1. **Clone o repositório**
```bash
git clone https://github.com/GabrielAzM/gptcode-site-ofc.git
cd gptcode-site-ofc
```

2. **Crie um ambiente virtual**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

4. **Execute a aplicação**
```bash
python app.py
```

5. **Acesse no navegador**
```
http://localhost:5000
```

---

## 🚀 Como Usar

### Estrutura do Flask

A aplicação usa o padrão de rotas simples no `app.py`:

```python
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/projetos')
def projetos():
    return render_template('projetos.html')

# ... outras rotas
```

### Adicionar uma Nova Página

1. **Crie o arquivo HTML em `templates/`**
```html
{% extends 'base.html' %}

{% block content %}
<!-- Seu conteúdo aqui -->
{% endblock %}
```

2. **Adicione a rota em `app.py`**
```python
@app.route('/nova-pagina')
def nova_pagina():
    return render_template('nova_pagina.html')
```

3. **Adicione link na navbar (`base.html`)**
```html
<li class="nav-item">
  <a class="nav-link" href="{{ url_for('nova_pagina') }}">Nova Página</a>
</li>
```

### Adicionar Estilos CSS

- Crie um arquivo `static/css/nova_pagina.css`
- Importe em `base.html`:
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/nova_pagina.css') }}" />
```

---

## 📄 Estrutura de Páginas

### 🏠 Página Inicial (`index.html`)
- **Hero Section**: Apresentação do grupo
- **Quem Somos**: Missão e visão
- **Destaques**: Projeto em destaque
- **Parceiros**: Logos de IFB e CNPq

### 🔬 Projetos (`projetos.html`)
- Grid de projetos categorizados
- PIBIC, PIBITI, TCC
- Informações de estudantes e orientadores

### 📚 Publicações (`publicacoes.html`)
- Lista de artigos publicados
- Links para leitura
- Filtros por categoria

### 👥 Equipe (`equipe.html`)
- Perfis de membros
- Fotos e informações
- Links para redes sociais

### 📞 Contato (`contato.html`)
- Formulário de contato
- Informações de contato
- Localização (mapa)

### 👨‍💻 Desenvolvedores (`devs.html`)
- Equipe de desenvolvimento
- Perfis dos desenvolvedores
- Tecnologias utilizadas

---

## 💡 Personalizações e Boas Práticas

### Hierarquia de Cores
Definidas em `:root` no `main.css`:
```css
:root {
  --dark-blue: #0b193e;          /* Azul escuro principal */
  --medium-blue: #427aa1;        /* Azul médio para destaques */
  --accent-gold: #6c757d;        /* Acentos dourados */
  --light-blue: #a5c9e0;         /* Azul claro */
  --light-text: #f8f9fa;         /* Texto claro */
  --dark-text: #212529;          /* Texto escuro */
}
```

### Sistema de Animações
Todos os `@keyframes` estão em `animacoes.css`:
- `fadeIn` (4.5s) - Fade in suave
- `slideInUp` (4s) - Slide de baixo para cima
- `slideInLeft` (3.5s) - Slide da esquerda
- `slideInRight` (3.5s) - Slide da direita
- `fadeInDown`, `fadeInLeft`, `fadeInRight`, `scaleIn`

### Classes de Delay
Delay classes (`delay-1` até `delay-10`) e stagger classes (`stagger-1` até `stagger-10`) para controlar timing de animações.

### Utility Classes
- `.contact-card-max-width` - Cards de contato
- `.dev-card-padding` - Padding para cards de desenvolvedores
- `.dev-image-cover` - Imagens com object-fit
- `.highlight-section` - Seções destacadas

---

## 📱 Responsividade

### Breakpoints Implementados

| Breakpoint | Largura | Uso |
|-----------|---------|-----|
| Ultra HD | 1920px+ | 4K displays |
| Desktop Grande | 1440-1919px | Monitores grandes |
| Desktop | 1024-1439px | Monitores padrão |
| Tablet Horizontal | 768-1023px | iPad landscape |
| Tablet | 640-767px | iPad portrait |
| Mobile Médio | 480-639px | Telefone landscape |
| Mobile Pequeno | 380-479px | Telefone pequeno |
| Ultra Mobile | <380px | Telefones antigos |

### Mobile-First Approach
- CSS base responsivo para mobile
- Media queries para dispositivos maiores
- Imagens adaptativas com `max-width: 100%`
- Fonts escaláveis com `rem` units

---

## 🎬 Animações

### Sistema de Animações Automático

O JavaScript automaticamente anima:
- **Headers/Heroes**: `fade-in` (4.5s)
- **Títulos**: `fade-in-down` (3.5s)
- **Cards/Seções**: `fade-in-up` (4s) com stagger
- **Imagens**: `fade-in-right` (3.5s)
- **Botões**: `fade-in-up` (4s)

### Ejemplo de Uso em HTML
```html
<h1 class="fade-in-up stagger-1">Título</h1>
<p class="fade-in-up stagger-2">Descrição</p>
<div class="card fade-in-up" style="animation-delay: 0.3s;">Conteúdo</div>
```

### IntersectionObserver
Elementos que entram na viewport recebem animação automática de `fade-in-up`.

---

## ⚡ Performance

### Otimizações Implementadas

1. **CSS Compacto**
   - ✅ Sem duplicação de estilos
   - ✅ Variáveis CSS reutilizáveis
   - ✅ Media queries organizadas

2. **JavaScript Eficiente**
   - ✅ Reduzido 40% (de 335 para 200 linhas)
   - ✅ Sem código duplicado
   - ✅ Event listeners consolidados
   - ✅ requestAnimationFrame para scroll

3. **HTML Semântico**
   - ✅ Sem código duplicado
   - ✅ Tags semânticas (`<header>`, `<section>`, `<footer>`)
   - ✅ Atributos acessibilidade

4. **Carregamento de Recursos**
   - ✅ Bootstrap CDN
   - ✅ Icons inline
   - ✅ Fonts Google (Poppins)

### Métricas

| Métrica | Antes | Depois |
|---------|-------|--------|
| Linhas main.js | 335 | 200 |
| CSS duplicado | 3x | 1x |
| HTML duplicado | Sim | Não |
| Performance Score | 78 | 95+ |

---

## 🔧 Troubleshooting

### Navbar desaparece ao scroll
**Solução**: Verifique se `navbar-scrolled` tem `background-color: white !important`

### Animações não aparecem
**Solução**: Limpe cache do navegador (Ctrl+Shift+R)

### Links da navbar invisíveis
**Solução**: Verificar cor dos `.navbar-dark .navbar-nav .nav-link` 
- Desktop: `rgba(0, 0, 0, 0.8)`
- Mobile: `rgba(255, 255, 255, 0.9)`

### Responsividade quebrada
**Solução**: Verificar se Bootstrap está carregado e media queries estão ativas

---

## 🤝 Contribuição

Contribuições são bem-vindas! Para contribuir:

1. Faça fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

### Padrões de Código

- Use HTML semântico
- Mantenha CSS modular
- Siga naming conventions (kebab-case para classes)
- Adicione comentários em código complexo
- Teste em diferentes tamanhos de tela

---

## 📝 Licença

Este projeto está licenciado sob a MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## 📞 Contato

**GPTCode - Grupo de Pesquisa em Tecnologias Computacionais**

- 📧 Email: [gptcode@gptcode.com.br](mailto:gptcode@gptcode.com.br)
- 📍 Endereço: SGAN Quadra 610 Módulos D, E, F, G - Asa Norte, Brasília - DF, 70830-450
- 🌐 Website: [gptcode.ifb.edu.br](https://gptcode.ifb.edu.br)
- 🐙 GitHub: [@GPTCodeIFB](https://github.com/GPTCodeIFB)
- 📷 Instagram: [@gptcodeifb](https://www.instagram.com/gptcodeifb/)

---

## 👥 Equipe de Desenvolvimento

Este projeto foi desenvolvido por:

- **Davi Rocha Fortes Bezerra** - Desenvolvedor Full Stack
- **Gabriel Azevedo Marques** - Desenvolvedor Full Stack
- **Lucas Henrique Ferreira Alves** - Desenvolvedor Front End/Product Owner
- **Luiz Gustavo Souza Batista** - Desenvolvedor Backend/Product Owner

Sob orientação de:
- **Prof. Dr. Dauster Souza Pereira** - Orientador

---

## 📊 Changelog

### v1.0.0 (5 de Dezembro de 2025)
- ✅ Refatoração completa do código
- ✅ Remoção de HTML duplicado
- ✅ Otimização de CSS (-66% duplicação)
- ✅ Refatoração JavaScript (-40% linhas)
- ✅ Sistema de animações completo
- ✅ Responsividade melhorada (8 breakpoints)
- ✅ Navbar permanentemente branca
- ✅ Footer com ícones sociais centralizados
- ✅ Boas práticas implementadas

---

## 🎉 Agradecimentos

Agradecimentos especiais a:
- **Instituto Federal de Brasília (IFB)** - Instituição anfitriã
- **CNPq** - Apoio à pesquisa
- **Comunidade Open Source** - Ferramentas e inspiração

---

**Desenvolvido com ❤️ pelo GPTCode**

*Última atualização: 5 de Dezembro de 2025*
