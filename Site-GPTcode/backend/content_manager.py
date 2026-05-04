from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"
CONTENT_FILE = DATA_DIR / "site_content.json"


DEFAULT_SITE_CONTENT: dict[str, Any] = {
    "home": {
        "hero": {
            "title": "Grupo de Pesquisa em Tecnologias Computacionais",
            "subtitle": "Desenvolvendo o futuro com codigo e inovacao no Instituto Federal de Brasilia.",
        },
        "about": {
            "title": "Quem somos",
            "lead": "O GPTCode e um grupo de pesquisa do Instituto Federal de Educacao, Ciencia e Tecnologia de Brasilia (IFB) dedicado ao desenvolvimento de tecnologias computacionais.",
            "description": "Nossa missao e criar solucoes que abordem problemas complexos e contribuam para o avanco cientifico e tecnologico da sociedade.",
            "primary_button_text": "Conheca nossa equipe",
            "primary_button_link": "/equipe",
            "secondary_button_text": "Nossas publicacoes",
            "secondary_button_link": "/publicacoes",
            "slider": [
                {
                    "id": "about-slide-1",
                    "image": "imagens/logos/gptcode-icon.png",
                    "alt": "Laboratorio GPTCode",
                }
            ],
        },
        "highlight": {
            "title": "Uso de Realidade Aumentada na conscientizacao do tabagismo",
            "authors": "Alessandro Aveni (UnB) e Claudio Ulisse (IFB)",
            "description": "Artigo discute o mercado de NFTs e as causas da crise, explorando questoes legais relacionadas ao sistema de propriedade intelectual, regulamentacoes de IA e incertezas do mercado NFT.",
            "journal": "Revista Processus de Estudos de Gestao, Juridicos e Financeiros",
            "image": "imagens/logos/Intellectual Property and the Future of NFT Market - logo.png",
            "image_alt": "Projeto em destaque",
            "primary_button_text": "Ver Publicacao",
            "primary_button_link": "/publicacoes",
            "secondary_button_text": "Ver mais Publicacoes",
            "secondary_button_link": "/publicacoes",
        },
        "partners_title": "Parceiros e Apoiadores",
        "partners": [
            {
                "id": "partner-ifb",
                "name": "Instituto Federal de Brasilia",
                "link": "https://www.ifb.edu.br",
                "image": "imagens/logos/Instituto_Federal_de_Brasília.png",
            },
            {
                "id": "partner-cnpq",
                "name": "CNPq",
                "link": "http://dgp.cnpq.br/dgp/espelhogrupo/812978",
                "image": "imagens/logos/cnpq-icon.png",
            },
        ],
    },
    "projects": {
        "page": {
            "title": "Projetos",
            "subtitle": "Conheca os projetos em andamento do GPTCode",
            "section_title": "Projetos em Andamento",
        },
        "items": [
            {
                "id": "project-pibic-2025-2026",
                "badge": "PIBIC 2025/2026",
                "title": "Desenvolvimento de um Sistema Web para Avaliacao Periodica de Curso de Graduacao no IFB - Campus Brasilia",
                "students": "Davi Rocha Fortes Bezerra",
                "advisor": "Prof. Dr. Dauster Souza Pereira",
                "image": "",
                "about_url": "",
            },
            {
                "id": "project-pibiti-2025-2026",
                "badge": "PIBITI 2025/2026",
                "title": "Game Based Learning (GBL) para o ensino de estrutura de dados: impactos na aprendizagem e engajamento",
                "students": "Mayara Vieira Martins Santos",
                "advisor": "Prof. Dr. Dauster Souza Pereira",
                "image": "",
                "about_url": "",
            },
            {
                "id": "project-dashboard-cpa-ifb",
                "badge": "PTCC/TCC",
                "title": "Dashboard de Autoavaliacao Institucional: uma ferramenta para a gestao e transparencia dos dados da CPA do IFB",
                "students": "Davi Campos Parente e Ivanilson Paixao Cirqueira",
                "advisor": "Prof. Dr. Dauster Souza Pereira",
                "image": "",
                "about_url": "",
            },
            {
                "id": "project-tabagismo-ar",
                "badge": "PTCC/TCC",
                "title": "Realidade Aumentada e Tabagismo",
                "students": "Luiz Fernando de Souza Dobbin",
                "advisor": "Prof. Dr. Dauster Souza Pereira",
                "image": "",
                "about_url": "",
            },
            {
                "id": "project-reddit-sentimentos",
                "badge": "PTCC/TCC",
                "title": "Analise de Sentimentos no Reddit: mensurando a opiniao publica sobre temas governamentais",
                "students": "Savio Vinicius Sousa",
                "advisor": "Prof. Dr. Dauster Souza Pereira",
                "image": "",
                "about_url": "",
            },
            {
                "id": "project-trilhas-cerrado",
                "badge": "PTCC/TCC",
                "title": "Plataforma de Agendamento Online para Trilhas no Cerrado",
                "students": "Leandro Souza Rocha e Gabriel G. S. Silva",
                "advisor": "Prof. Dr. Dauster Souza Pereira",
                "image": "",
                "about_url": "",
            },
            {
                "id": "project-ra-informatica-basica",
                "badge": "PTCC/TCC",
                "title": "Realidade Aumentada no Ensino de Informatica Basica: prototipagem criativa com design thinking",
                "students": "Alice Alves da Gama e Luidy Baldez de Melo",
                "advisor": "Prof. Dr. Dauster Souza Pereira",
                "image": "",
                "about_url": "",
            },
            {
                "id": "project-impactos-ia-generativa",
                "badge": "PTCC/TCC",
                "title": "Impactos Ambientais da IA Generativa: analise de relatorios ESG de big techs e proposta de indicadores transparentes",
                "students": "Mateus Nascimento Aires",
                "advisor": "Prof. Dr. Dauster Souza Pereira",
                "image": "",
                "about_url": "",
            },
            {
                "id": "project-site-gptcode",
                "badge": "Outros Projetos",
                "title": "Desenvolvimento do Site GPTCode",
                "students": "Davi Rocha Fortes Bezerra e Gabriel Azevedo Marques",
                "advisor": "Prof. Dr. Dauster Souza Pereira",
                "image": "",
                "about_url": "",
            },
        ],
    },
    "publications": {
        "page": {
            "title": "Publicacoes",
            "subtitle": "Producao cientifica e tecnica do grupo de pesquisa",
            "section_title": "Publicacoes Cientificas",
        },
        "items": [
            {
                "id": "publication-2023-1",
                "year": "2023",
                "title": "Uma analise de satisfacao do uso de hipermidias em um aplicativo para dispositivo movel de educacao em saude",
                "participants": "PEREIRA, Dauster Souza; DE LIMA, Jose Valdeni; CONCEICAO, S. C. O.; GOMES, R. S.; ROCHA, P. S.; JARDIM, R. R.; JOFILSAN, N. C.; PEREIRA, P. P. S.",
                "journal": "REVISTA IBEROAMERICANA DE TECNOLOGIA EN EDUCACION Y EDUCACION EN TECNOLOGIA (EN LINEA), v. 34, p. e2-29, 2023.",
                "doi_url": "https://teyet-revista.info.unlp.edu.ar/TEyET/article/view/2159",
            },
            {
                "id": "publication-2023-2",
                "year": "2023",
                "title": "Intervencion Educativa Virtual sobre Nutricion en Adolescentes",
                "participants": "SILVA, Joao; SANTOS, Maria; OLIVEIRA, Pedro",
                "journal": "Revista de Educacao Nutricional, v. 12, n. 3, 2023.",
                "doi_url": "https://respyn.uanl.mx/index.php/respyn/article/view/730?articlesBySimilarityPage=7",
            },
            {
                "id": "publication-2022-1",
                "year": "2022",
                "title": "Use of Information and Communication Technologies in Higher Education",
                "participants": "RODRIGUES, Ana; COSTA, Carlos; FERREIRA, Diana",
                "journal": "International Journal of Educational Technology, v. 10, n. 2, pp. 156-172, 2022.",
                "doi_url": "https://periodicos.ufmg.br/index.php/edrevista/article/view/45465?articlesBySimilarityPage=21",
            },
            {
                "id": "publication-2021-1",
                "year": "2021",
                "title": "Modelo Visual Baseado em Blocos para Programacao Educativa",
                "participants": "PEREIRA, Dauster; GOMES, Ricardo; SANTOS, Luiz",
                "journal": "Revista Brasileira de Informatica na Educacao, v. 29, n. 1, 2021.",
                "doi_url": "",
            },
            {
                "id": "publication-2021-2",
                "year": "2021",
                "title": "Hipermidias em Dispositivos Moveis: Aplicacoes Educacionais",
                "participants": "DE LIMA, Jose Valdeni; CONCEICAO, Simone; JARDIM, Roberta",
                "journal": "Journal of Mobile Learning and Computing, v. 8, n. 4, 2021.",
                "doi_url": "",
            },
            {
                "id": "publication-2019-1",
                "year": "2019",
                "title": "Educational Games: Effectiveness and Learning Outcomes",
                "participants": "PEREIRA, Dauster; ROCHA, Paulo; GOMES, Ricardo",
                "journal": "Computers & Education, v. 141, 2019.",
                "doi_url": "",
            },
            {
                "id": "publication-2019-2",
                "year": "2019",
                "title": "HTML5 Authoring Tool for Multimedia Content Creation",
                "participants": "SANTOS, Luiz; OLIVEIRA, Pedro; SILVA, Joao",
                "journal": "IEEE Transactions on Learning Technologies, v. 12, n. 3, 2019.",
                "doi_url": "",
            },
            {
                "id": "publication-2019-3",
                "year": "2019",
                "title": "Praticas com Simulacoes Computacionais em Ambientes de Aprendizagem",
                "participants": "CONCEICAO, Simone; JARDIM, Roberta; SANTOS, Luiz",
                "journal": "Revista de Informatica Teorica e Aplicada, v. 26, n. 2, 2019.",
                "doi_url": "",
            },
            {
                "id": "publication-2018-1",
                "year": "2018",
                "title": "Modelando Trajetorias de Aprendizagem em Ambientes Virtuais",
                "participants": "PEREIRA, Dauster; GOMES, Ricardo; ROCHA, Paulo",
                "journal": "Journal of Educational Computing Research, v. 56, n. 8, 2018.",
                "doi_url": "",
            },
            {
                "id": "publication-2018-2",
                "year": "2018",
                "title": "A Robotica Educativa como Ferramenta de Ensino de Programacao",
                "participants": "SANTOS, Luiz; SILVA, Joao; OLIVEIRA, Pedro",
                "journal": "Proceedings of the Conference on Technology in Education, 2018.",
                "doi_url": "",
            },
        ],
    },
    "team": {
        "page": {
            "title": "Nossa Equipe",
            "subtitle": "Conheca os pesquisadores, alunos e colaboradores do GPTCode",
        },
        "categories": [
            {
                "id": "professores",
                "title": "Professores Pesquisadores",
                "empty_message": "Nenhum membro por enquanto",
            },
            {
                "id": "graduacao",
                "title": "Alunos de Graduacao",
                "empty_message": "Nenhum membro por enquanto",
            },
            {
                "id": "tecnico",
                "title": "Alunos Tecnicos",
                "empty_message": "Nenhum membro por enquanto",
            },
            {
                "id": "externos",
                "title": "Ex-Alunos do IFB e/ou Colaboradores Externos",
                "empty_message": "Nenhum membro por enquanto",
            },
        ],
        "members": [
            {
                "id": "member-dauster",
                "category": "professores",
                "name": "Prof. Dr. Dauster Souza Pereira",
                "role": "Coordenador",
                "github_url": "https://github.com/usuario",
                "lattes_url": "",
                "description": "Doutor em Informatica na Educacao pela UFRGS, professor do IFB e apaixonado por tecnologia.",
                "tags": ["Educacao", "Tecnologia", "Pesquisa"],
                "image": "imagens/equipe/professores/Dauster.jpeg",
            },
            {
                "id": "member-claudio",
                "category": "professores",
                "name": "Prof. Me. Claudio Ulisse",
                "role": "Professor Pesquisador",
                "github_url": "https://github.com/claulis/",
                "lattes_url": "",
                "description": "Professor de Ciencia da Computacao com Bacharelado em Sistemas de Informacao. Mestre em Propriedade Intelectual e Transferencia de Tecnologia para Inovacao. Analista de sistemas e desenvolvedor web experiente, com expertise em integracao de sistemas e arquitetura distribuida.",
                "tags": ["Educacao", "Tecnologia", "Pesquisa"],
                "image": "imagens/equipe/professores/claudio.jpeg",
            },
            {
                "id": "member-fernando",
                "category": "professores",
                "name": "Prof. Me. Fernando Wagner Brito Hortencio Filho",
                "role": "Professor Pesquisador",
                "github_url": "",
                "lattes_url": "",
                "description": "Mestre em Ciencia da Computacao com expertise em desenvolvimento de software, arquitetura de sistemas e metodologias ageis. Professor dedicado a formacao de novos talentos em tecnologia.",
                "tags": ["Desenvolvimento", "Arquitetura", "Metodologias Ageis"],
                "image": "imagens/equipe/professores/Fernando Wagner.jpeg",
            },
            {
                "id": "member-sylvana",
                "category": "professores",
                "name": "Profa. Dra. Sylvana Karla da Silva de Lemos Santos",
                "role": "Professora Pesquisadora",
                "github_url": "",
                "lattes_url": "",
                "description": "Doutora em Ciencia da Computacao com especializacao em inteligencia artificial, machine learning e analise de dados. Pesquisadora ativa em tecnologias emergentes e inovacao educacional.",
                "tags": ["IA", "Machine Learning", "Analise de Dados"],
                "image": "imagens/equipe/professores/Sylvana.jpeg",
            },
            {
                "id": "member-gabriel-azevedo",
                "category": "graduacao",
                "name": "Gabriel Azevedo Marques",
                "role": "Aluno de Graduacao",
                "github_url": "https://github.com/SkyWallker616",
                "lattes_url": "",
                "description": "Formado em Tecnico em Desenvolvimento de Sistemas pelo IFB. Cursa Tecnologias em Sistemas para Internet (TSI) pelo IFB e Ciencias da Computacao pela Universidade Estacio.",
                "tags": ["Python", "Desenvolvimento Web", "Front-end"],
                "image": "imagens/equipe/alunos/graduacao/gabriel.azevedo.jpeg",
            },
            {
                "id": "member-davi-rocha",
                "category": "graduacao",
                "name": "Davi Rocha Fortes Bezerra",
                "role": "Aluno de Graduacao",
                "github_url": "https://github.com/davirfb",
                "lattes_url": "",
                "description": "Estudante do IFB no curso de Tecnologo em Sistemas para Internet (TSI). Apaixonado por desenvolvimento web e tecnologias emergentes, com interesse em front-end e experiencia do usuario.",
                "tags": ["Desenvolvimento Web", "Front-end", "UX/UI"],
                "image": "imagens/equipe/alunos/graduacao/Davi.png",
            },
            {
                "id": "member-alice",
                "category": "graduacao",
                "name": "Alice Alves da Gama",
                "role": "Aluna de Graduacao",
                "github_url": "https://github.com/AliceAlvesG",
                "lattes_url": "",
                "description": "Estudante dedicada com interesse em desenvolvimento de software e tecnologias emergentes. Focada em aprender novas linguagens de programacao e metodologias de desenvolvimento.",
                "tags": ["Programacao", "Desenvolvimento", "Tecnologia"],
                "image": "imagens/equipe/alunos/graduacao/Alice Alves da Gama.jpeg",
            },
            {
                "id": "member-luidy",
                "category": "graduacao",
                "name": "Luidy Baldez de Melo",
                "role": "Aluno de Graduacao",
                "github_url": "https://github.com/lBALDEZl",
                "lattes_url": "",
                "description": "Estudante com paixao por tecnologia e inovacao. Interessado em desenvolvimento de sistemas e solucoes computacionais que impactem positivamente a sociedade.",
                "tags": ["Sistemas", "Inovacao", "Tecnologia"],
                "image": "imagens/equipe/alunos/graduacao/Luidy Baldez.jpeg",
            },
            {
                "id": "member-davi-parente",
                "category": "graduacao",
                "name": "Davi Campos Parente",
                "role": "Aluno de Graduacao",
                "github_url": "https://github.com/DaviParente10",
                "lattes_url": "",
                "description": "Estudante entusiasta da area de computacao, com foco em desenvolvimento de software e pesquisa em tecnologias computacionais avancadas.",
                "tags": ["Software", "Pesquisa", "Computacao"],
                "image": "imagens/equipe/alunos/graduacao/Davi Campos Parente.jpeg",
            },
            {
                "id": "member-eduardo",
                "category": "graduacao",
                "name": "Eduardo Rodrigues Estrela",
                "role": "Aluno de Graduacao",
                "github_url": "https://github.com/EduardoStarZ",
                "lattes_url": "",
                "description": "Estudante comprometido com a excelencia academica.",
                "tags": ["IA", "Machine Learning", "Pesquisa"],
                "image": "imagens/equipe/alunos/graduacao/Eduardo Rodrigues Estrela.jpeg",
            },
            {
                "id": "member-gabriel-goncalves",
                "category": "graduacao",
                "name": "Gabriel Goncalves dos Santos Silva",
                "role": "Aluno de Graduacao",
                "github_url": "https://github.com/Gabriel25484",
                "lattes_url": "",
                "description": "Estudante dedicado com interesse em desenvolvimento full-stack e arquitetura de software. Busca sempre aprender novas tecnologias e aplica-las em projetos praticos.",
                "tags": ["Full-stack", "Arquitetura", "Desenvolvimento"],
                "image": "imagens/equipe/alunos/graduacao/Gabriel Gonçalves dos Santos Silva.jpeg",
            },
            {
                "id": "member-ivanilson",
                "category": "graduacao",
                "name": "Ivanilson Paixao Cirqueira",
                "role": "Aluno de Graduacao",
                "github_url": "https://github.com/ivanilsonstfler",
                "lattes_url": "",
                "description": "Estudante apaixonado por tecnologia e inovacao, com foco em desenvolvimento de aplicacoes web e mobile. Interessado em UX/UI e experiencia do usuario.",
                "tags": ["Web", "Mobile", "UX/UI"],
                "image": "imagens/equipe/alunos/graduacao/Ivanilson Paixão Cirqueira.jpeg",
            },
            {
                "id": "member-leandro",
                "category": "graduacao",
                "name": "Leandro Souza Rocha",
                "role": "Aluno de Graduacao",
                "github_url": "https://github.com/Leandrorocha17",
                "lattes_url": "",
                "description": "Estudante com interesse em seguranca da informacao e desenvolvimento de sistemas seguros. Busca contribuir para a criacao de solucoes tecnologicas robustas.",
                "tags": ["Seguranca", "Sistemas", "Desenvolvimento"],
                "image": "imagens/equipe/alunos/graduacao/Leandro Souza Rocha.jpeg",
            },
            {
                "id": "member-mateus",
                "category": "graduacao",
                "name": "Mateus Nascimento Aires",
                "role": "Aluno de Graduacao",
                "github_url": "https://github.com/mateuaires",
                "lattes_url": "",
                "description": "Estudante entusiasta da programacao e desenvolvimento de software, com interesse especial em algoritmos e estruturas de dados. Sempre buscando otimizar solucoes.",
                "tags": ["Algoritmos", "Estruturas", "Otimizacao"],
                "image": "imagens/equipe/alunos/graduacao/Mateus Nascimento Aires.jpeg",
            },
            {
                "id": "member-mayara",
                "category": "graduacao",
                "name": "Mayara Vieira Martins Santos",
                "role": "Aluna de Graduacao",
                "github_url": "https://github.com/MayaraVieiraa",
                "lattes_url": "",
                "description": "Estudante dedicada com interesse em analise de dados e business intelligence. Focada em transformar dados em insights valiosos para tomada de decisoes.",
                "tags": ["Dados", "BI", "Analytics"],
                "image": "imagens/equipe/alunos/graduacao/Mayara Vieira Martins Santos.png",
            },
            {
                "id": "member-savio",
                "category": "graduacao",
                "name": "Savio Vinicius de Sousa",
                "role": "Aluno de Graduacao",
                "github_url": "https://github.com/savifb",
                "lattes_url": "",
                "description": "Estudante com paixao por desenvolvimento backend e arquitetura de sistemas. Interessado em criar solucoes escalaveis e eficientes para problemas complexos.",
                "tags": ["Backend", "Arquitetura", "Escalabilidade"],
                "image": "imagens/equipe/alunos/graduacao/Sávio Vinícius de Sousa.jpg",
            },
            {
                "id": "member-vitoria",
                "category": "graduacao",
                "name": "Vitoria Santana Silva",
                "role": "Aluna de Graduacao",
                "github_url": "https://github.com/VII-Z",
                "lattes_url": "",
                "description": "Estudante com interesse em desenvolvimento frontend e design de interfaces. Focada em criar experiencias digitais intuitivas e acessiveis para todos os usuarios.",
                "tags": ["Frontend", "Design", "Acessibilidade"],
                "image": "imagens/equipe/alunos/graduacao/Vitória Santana Silva.jpg",
            },
            {
                "id": "member-andersen",
                "category": "externos",
                "name": "Andersen Gonzaga Facundo",
                "role": "",
                "github_url": "https://github.com/andersengf",
                "lattes_url": "",
                "description": "",
                "tags": [],
                "image": "imagens/equipe/alunos/ExAlunos do IFB e ou Colaboradores Externos/Andersen Gonzaga Facundo.jpeg",
            },
            {
                "id": "member-anderson",
                "category": "externos",
                "name": "Anderson de Castro Gomes",
                "role": "",
                "github_url": "https://github.com/AndersonCastroGomes",
                "lattes_url": "",
                "description": "",
                "tags": [],
                "image": "imagens/equipe/alunos/ExAlunos do IFB e ou Colaboradores Externos/Anderson de Castro Gomes.png",
            },
            {
                "id": "member-edilson",
                "category": "externos",
                "name": "Edilson Nery Barbosa",
                "role": "",
                "github_url": "https://github.com/edilsonnerybarbosa",
                "lattes_url": "",
                "description": "",
                "tags": [],
                "image": "imagens/equipe/alunos/ExAlunos do IFB e ou Colaboradores Externos/Edilson Nery Barbosa.jpeg",
            },
            {
                "id": "member-fernando-fabio",
                "category": "externos",
                "name": "Fernando Fabio Inocencio Cavalcante",
                "role": "",
                "github_url": "https://github.com/FernandoFIC",
                "lattes_url": "",
                "description": "",
                "tags": [],
                "image": "imagens/equipe/alunos/ExAlunos do IFB e ou Colaboradores Externos/Fernando Fábio Inocêncio Cavalcante.jpeg",
            },
        ],
    },
}


def _merge_defaults(default_value: Any, current_value: Any) -> Any:
    if isinstance(default_value, dict):
        current_value = current_value if isinstance(current_value, dict) else {}
        merged: dict[str, Any] = {}
        for key, value in default_value.items():
            merged[key] = _merge_defaults(value, current_value.get(key))
        for key, value in current_value.items():
            if key not in merged:
                merged[key] = value
        return merged

    if isinstance(default_value, list):
        return current_value if isinstance(current_value, list) else deepcopy(default_value)

    return default_value if current_value is None else current_value


def get_default_site_content() -> dict[str, Any]:
    return deepcopy(DEFAULT_SITE_CONTENT)


def save_site_content(content: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with CONTENT_FILE.open("w", encoding="utf-8") as file:
        json.dump(content, file, ensure_ascii=False, indent=2)


def ensure_site_content() -> None:
    if not CONTENT_FILE.exists():
        save_site_content(get_default_site_content())


def load_site_content() -> dict[str, Any]:
    ensure_site_content()
    with CONTENT_FILE.open("r", encoding="utf-8") as file:
        content = json.load(file)
    merged_content = _merge_defaults(get_default_site_content(), content)
    if merged_content != content:
        save_site_content(merged_content)
    return merged_content
