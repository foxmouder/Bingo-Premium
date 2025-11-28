import customtkinter as ctk
from customtkinter import CTk, CTkFrame, CTkLabel, CTkEntry, CTkButton, CTkTextbox, CTkScrollableFrame
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import random
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import pandas as pd
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os
from datetime import datetime
import json
import sys
import time
import threading

# --- Variáveis Globais de Configuração ---
# O NUMERO_MAXIMO agora é uma variável de instância na classe BingoSystem, mas mantemos o default
DEFAULT_NUMERO_MAXIMO = 75 
DEFAULT_TOTAL_CARTELAS = 126
VERSAO_SISTEMA = "v7.0.0 Plus" # Versão Plus [MODIFICADO]

# --- Sistema de Logs ---
LOG_FILE = 'system.log'
ERROR_LOG_FILE = 'error.log'

def log_message(level, message):
    """Gera uma mensagem de log no console e salva em arquivo."""
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    log_entry = f"{timestamp} [{level}] {message}"
    print(log_entry)
    
    try:
        if level == "ERROR":
            with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    except Exception as e:
        print(f"Erro ao escrever log em arquivo: {e}")

# --- Classe Tooltip Simples (Mantida) ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.tw_id = None
        self.widget.bind("<Enter>", self.schedule_show)
        self.widget.bind("<Leave>", self.schedule_hide)
        self.widget.bind("<ButtonPress>", self.schedule_hide)

    def schedule_show(self, event=None):
        """Agenda a exibição do tooltip após 0.5s."""
        self.schedule_hide()
        if self.tw_id is None:
            self.tw_id = self.widget.after(500, self.showtip)

    def schedule_hide(self, event=None):
        """Cancela a exibição ou agenda o fechamento."""
        if self.tw_id:
            self.widget.after_cancel(self.tw_id)
            self.tw_id = None
        
        if self.tipwindow:
            self.tipwindow.after(100, self.hidetip)

    def showtip(self):
        """Exibe o texto do tooltip."""
        self.tw_id = None
        if self.tipwindow or not self.text:
            return
        
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() - 30
        
        self.tipwindow = ctk.CTkToplevel(self.widget)
        self.tipwindow.wm_overrideredirect(True)
        
        label = ctk.CTkLabel(self.tipwindow, text=self.text, justify=tk.LEFT,
                             fg_color="#FFFFE0",  # Amarelo claro
                             text_color="#333333", # Texto escuro
                             corner_radius=5)
        label.pack(ipadx=7, ipady=3)
        
        # Centraliza o tooltip sobre o widget
        self.tipwindow.update_idletasks() 
        self.tipwindow.wm_geometry(f"+{x - (label.winfo_reqwidth() // 2)}+{y}")
        self.tipwindow.lift(self.widget.winfo_toplevel())

    def hidetip(self):
        """Esconde o tooltip."""
        if self.tipwindow:
            self.tipwindow.destroy()
        self.tipwindow = None

# --- Classe LoadingWindow (Mantida) ---
class LoadingWindow:
    """Janela de carregamento para processos demorados"""
    
    def __init__(self, parent, title="Processando..."):
        self.parent = parent
        self.window = ctk.CTkToplevel(parent)
        self.window.title(title)
        self.window.geometry("300x150")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.window.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (300 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (150 // 2)
        self.window.geometry(f"+{x}+{y}")
        
        CTkLabel(self.window, text=title, font=("Arial", 16, "bold")).pack(pady=20)
        
        self.progress = ctk.CTkProgressBar(self.window, width=250)
        self.progress.pack(pady=10)
        self.progress.set(0)
        
        self.status_label = CTkLabel(self.window, text="Iniciando...", font=("Arial", 12))
        self.status_label.pack(pady=10)
        
    def update_progress(self, value, status=""):
        """Atualiza a barra de progresso"""
        try:
            self.progress.set(value)
            if status:
                self.status_label.configure(text=status)
            self.window.update()
        except tk.TclError:
            pass
        
    def close(self):
        """Fecha a janela de carregamento"""
        try:
            self.window.destroy()
        except:
            pass

# --- Classe BingoSystem ---
class BingoSystem:
    def __init__(self):
        log_message("INFO", "Iniciando Sistema de Bingo...")
        
        self.root = CTk()
        self.root.title(f"Sistema de Bingo Premium - Danilo Leão ({VERSAO_SISTEMA})")
        self.root.geometry("1000x700")
        self.root.minsize(900, 600)
        
        # 🚀 CORREÇÃO: Maximiza a janela ao iniciar
        self.root.state('zoomed')

        # 🎨 NOVAS CORES: Fundo Branco (Light) e tema padrão (blue) [MODIFICADO]
        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")
        
        # --- Variáveis do Estado do Concurso ---
        self.cartelas = {}
        self.compradores = {}
        self.numeros_sorteados = set()
        self.cartela_vencedora = None 
        self.historico_sorteios = []
        self.ultimo_numero_sorteado = None
        self.concursos = {}  
        self.concurso_atual = "Principal"  
        self.cartelas_geradas_uma_vez = False # [ADICIONADO] Flag para restrição de geração
        
        # --- NOVAS VARIÁVEIS DE CONFIGURAÇÃO ---
        self.numero_maximo = DEFAULT_NUMERO_MAXIMO
        self.total_cartelas = DEFAULT_TOTAL_CARTELAS
      
        self.setup_directories()
        self.load_data()
        
        # 🔒 CONTROLE: Flag para bloquear ações críticas se as cartelas base existirem
        self.cartelas_geradas = len(self.cartelas) > 0
        log_message("INFO", f"Estado inicial: Cartelas Geradas = {self.cartelas_geradas}")
        
        # [ADICIONADO] Se carregou dados e há cartelas, a geração já ocorreu uma vez
        if self.cartelas_geradas:
            self.cartelas_geradas_uma_vez = True 
            log_message("INFO", "Cartelas já existiam ao carregar. Geração única definida como True.")

        self.setup_ui()
        
        # Atualiza o estado da UI baseado no carregamento de dados
        self.update_ui_state()

        
    # --- Métodos de Configuração e Dados ---
    # ... (center_window, setup_directories, load_data, save_data - Mantidos, com ajustes na load/save para as novas variáveis)
    
    def center_window(self):
        # Esta função de centralizar será ignorada pelo state('zoomed'),
        # mas é mantida por segurança caso o state seja alterado.
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def setup_directories(self):
        os.makedirs('data', exist_ok=True)
        os.makedirs('exports', exist_ok=True)
        os.makedirs('temp', exist_ok=True)
        os.makedirs('concursos', exist_ok=True) 
        os.makedirs('backups', exist_ok=True) # [ADICIONADO] Diretório de backup
        
    def load_data(self):
        try:
            if os.path.exists('data/compradores.json'):
                with open('data/compradores.json', 'r', encoding='utf-8') as f:
                    self.compradores = json.load(f)
                    
            if os.path.exists('data/cartelas.json'):
                with open('data/cartelas.json', 'r', encoding='utf-8') as f:
                    self.cartelas = json.load(f)
           
            if os.path.exists('data/sorteio.json'):
                with open('data/sorteio.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.numeros_sorteados = set(data.get('numeros_sorteados', []))
                    self.cartela_vencedora = data.get('cartela_vencedora') 
                    self.historico_sorteios = data.get('historico_sorteios', [])
                    self.ultimo_numero_sorteado = data.get('ultimo_numero_sorteado')

            if os.path.exists('data/concursos.json'):
                with open('data/concursos.json', 'r', encoding='utf-8') as f:
                    self.concursos = json.load(f)
            
            # [ADICIONADO] Carrega a flag de restrição de geração e as NOVAS variáveis
            if os.path.exists('data/meta.json'):
                with open('data/meta.json', 'r', encoding='utf-8') as f:
                    meta_data = json.load(f)
                    self.cartelas_geradas_uma_vez = meta_data.get('cartelas_geradas_uma_vez', False)
                    # Carrega as novas configurações de geração [ADICIONADO]
                    self.numero_maximo = meta_data.get('numero_maximo', DEFAULT_NUMERO_MAXIMO)
                    self.total_cartelas = meta_data.get('total_cartelas', DEFAULT_TOTAL_CARTELAS)
                    log_message("INFO", f"Meta data carregada: cartelas_geradas_uma_vez={self.cartelas_geradas_uma_vez}, Max={self.numero_maximo}, Total={self.total_cartelas}")
            
            log_message("INFO", "Dados carregados com sucesso.")
                    
        except Exception as e:
            log_message("ERROR", f"Erro ao carregar dados salvos: {e}")
            
    def save_data(self):
        try:
            with open('data/compradores.json', 'w', encoding='utf-8') as f:
                json.dump(self.compradores, f, ensure_ascii=False, indent=2)
               
            with open('data/cartelas.json', 'w', encoding='utf-8') as f:
                json.dump(self.cartelas, f, ensure_ascii=False, indent=2)
                
            with open('data/sorteio.json', 'w', encoding='utf-8') as f:
                data = {
                    'numeros_sorteados': list(self.numeros_sorteados),
                    'cartela_vencedora': self.cartela_vencedora,
                    'historico_sorteios': self.historico_sorteios,
                    'ultimo_numero_sorteado': self.ultimo_numero_sorteado
                }
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            with open('data/concursos.json', 'w', encoding='utf-8') as f:
                json.dump(self.concursos, f, ensure_ascii=False, indent=2)

            # [ADICIONADO] Salva a flag de restrição de geração e as NOVAS variáveis
            meta_data = {
                'cartelas_geradas_uma_vez': self.cartelas_geradas_uma_vez,
                'numero_maximo': self.numero_maximo,
                'total_cartelas': self.total_cartelas
            }
            with open('data/meta.json', 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
            
            log_message("INFO", "Dados salvos com sucesso.")
                
        except Exception as e:
            log_message("ERROR", f"Erro ao salvar dados: {e}")

    # --- Métodos de UI (Integração e Layout - Mantidos) ---
    def setup_ui(self):
        self.center_window()
        self.main_frame = CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.create_header()
        self.create_tabs()
        self.create_footer()
    
    def create_header(self):
        header_frame = CTkFrame(self.main_frame, height=80)
        header_frame.pack(fill="x", padx=10, pady=(0, 10))
        header_frame.pack_propagate(False)
        
        title_label = CTkLabel(header_frame, 
                                 text="🎯 SISTEMA DE BINGO PREMIUM",
                                 font=("Arial", 24, "bold"),
                                 text_color="#2E86AB")
        title_label.pack(pady=20)
        
        status_frame = CTkFrame(self.main_frame, height=30)
        status_frame.pack(fill="x", padx=10, pady=(0, 5))
        status_frame.pack_propagate(False)
        
        self.status_label = CTkLabel(status_frame, text="", font=("Arial", 10))
        self.status_label.pack(side="left", padx=10)
        self.atualizar_status()
        
    def create_tabs(self):
        self.tab_frame = CTkFrame(self.main_frame)
        self.tab_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        tab_buttons_frame = CTkFrame(self.tab_frame)
        tab_buttons_frame.pack(fill="x", padx=5, pady=5)
        
        tabs_info = [
            ("🏠 Início", self.show_home, "Voltar para o painel principal."),
            ("👥 Compradores", self.show_compradores, "Cadastrar compradores e gerenciar cartelas vendidas."),
            ("🎫 Cartelas", self.show_cartelas, "Gerar, visualizar e exportar cartelas para impressão."),
            ("🎲 Sorteio", self.show_sorteio, "Realizar o sorteio de números e verificar o vencedor."),
            ("📊 Relatórios", self.show_relatorios, "Ver estatísticas, top cartelas e dados de compradores."),
            ("⚙️ Concursos", self.show_concursos, "Salvar e carregar diferentes concursos de bingo.")
        ]
        
        self.tab_buttons = []
        for i, (text, command, tooltip_text) in enumerate(tabs_info):
            btn = CTkButton(tab_buttons_frame, text=text, command=command,
                            font=("Arial", 12, "bold"), width=120, height=35)
            btn.pack(side="left", padx=2)
            self.tab_buttons.append(btn)
            self.add_tooltip_and_status(btn, tooltip_text) # Adiciona tooltip e status
        
        self.content_frame = CTkFrame(self.tab_frame)
        self.content_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.show_home()
        
    def create_footer(self):
        footer_frame = CTkFrame(self.main_frame, height=40)
        footer_frame.pack(fill="x", padx=10, pady=(5, 0))
        footer_frame.pack_propagate(False)
        
        self.copyright_label = CTkLabel(footer_frame, 
                                 text=f"© 2024 Danilo Leão - Sistema de Bingo Premium {VERSAO_SISTEMA}",
                                 font=("Arial", 10, "italic"),
                                 text_color="#666666")
        self.copyright_label.pack(side="left", padx=20)
        
        version_label = CTkLabel(footer_frame, 
                                 text=VERSAO_SISTEMA,
                                 font=("Arial", 10),
                                 text_color="#666666")
        version_label.pack(side="right", padx=20)

    def clear_content_frame(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
    def highlight_tab(self, index):
        default_fg_color = ctk.ThemeManager.theme['CTkButton']['fg_color']
        hover_fg_color = ctk.ThemeManager.theme['CTkButton']['hover_color']
        
        for i, btn in enumerate(self.tab_buttons):
            if i == index:
                btn.configure(fg_color=hover_fg_color)
            else:
                btn.configure(fg_color=default_fg_color)
                
    def atualizar_status(self):
        cartelas_vendidas = sum(1 for c in self.cartelas.values() if c.get('comprador_id'))
        
        status_text = (f"Concurso: {self.concurso_atual} | "
                       f"Cartelas: {len(self.cartelas)} ({cartelas_vendidas} vendidas) | "
                       f"Compradores: {len(self.compradores)} | "
                       f"Sorteados: {len(self.numeros_sorteados)}/{self.numero_maximo}") # [MODIFICADO]
        self.status_label.configure(text=status_text)

    def add_tooltip_and_status(self, widget, text):
        """Adiciona Tooltip e função de hover para barra de status."""
        tooltip = ToolTip(widget, text)
        
        # Evento de entrada (Mouse-over) - Atualiza a barra de status
        widget.bind("<Enter>", lambda e: self.copyright_label.configure(text=text), add="+")
        
        # Evento de saída (Mouse-out) - Volta ao texto padrão da barra de status
        widget.bind("<Leave>", lambda e: self.copyright_label.configure(
            text=f"© 2024 Danilo Leão - Sistema de Bingo Premium {VERSAO_SISTEMA}"), add="+")

    def update_ui_state(self):
        """Habilita/Desabilita botões baseado no estado de self.cartelas_geradas."""
        state = "normal" if self.cartelas_geradas else "disabled"
        log_message("INFO", f"Atualizando estado da UI para: {state}")

        # Botões principais (Abas) - Índice: 1:Compradores, 2:Cartelas, 3:Sorteio, 4:Relatórios
        if len(self.tab_buttons) >= 5:
             # Compradores (1)
            self.tab_buttons[1].configure(state=state)
             # Cartelas (2)
            self.tab_buttons[2].configure(state=state)
            # Sorteio (3)
            self.tab_buttons[3].configure(state=state)
            # Relatórios (4)
            self.tab_buttons[4].configure(state=state)

        # Se estiver na aba atual, re-cria a aba para refletir o novo estado (necessário para a HOME)
        current_tab_index = -1
        for i, btn in enumerate(self.tab_buttons):
            if btn.cget("fg_color") == ctk.ThemeManager.theme['CTkButton']['hover_color']:
                current_tab_index = i
                break
        
        if current_tab_index == 0:
             self.show_home() # Re-cria a HOME para atualizar os botões rápidos
        elif current_tab_index == 1:
             self.show_compradores() # Re-cria a Compradores
        elif current_tab_index == 2:
             self.show_cartelas() # Re-cria a Cartelas
        elif current_tab_index == 3:
             self.show_sorteio() # Re-cria a Sorteio
        elif current_tab_index == 4:
             self.show_relatorios() # Re-cria a Relatórios
        # A aba Concursos não precisa de re-criação completa pois a maioria dos seus botões não depende de cartelas_geradas


    # --- SHOW TELAS ---
    
    def show_home(self):
        self.clear_content_frame()
        self.highlight_tab(0)
        
        content = CTkFrame(self.content_frame)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        CTkLabel(content, text="Bem-vindo ao Sistema de Bingo Premium",
                                 font=("Arial", 20, "bold")).pack(pady=20)
        
        concurso_frame = CTkFrame(content)
        concurso_frame.pack(fill="x", pady=10)
        
        CTkLabel(concurso_frame, text=f"Concurso Atual: {self.concurso_atual}", 
                 font=("Arial", 14, "bold"), text_color="#2E86AB").pack(pady=5)
        
        stats_frame = CTkFrame(content)
        stats_frame.pack(fill="x", pady=20)
        
        stats_data = [
            ("📊 Total de Cartelas", len(self.cartelas), "#4CAF50"),
            ("👥 Compradores", len(self.compradores), "#2196F3"),
            ("🎲 Números Sorteados", f"{len(self.numeros_sorteados)}/{self.numero_maximo}", "#FF9800"), # [MODIFICADO]
            ("🏆 Cartela Vencedora", "Definida" if self.cartela_vencedora else "Não", "#F44336")
        ]
        
        for i, (title, value, color) in enumerate(stats_data):
            stat_card = CTkFrame(stats_frame, width=200, height=100)
            stat_card.pack(side="left", expand=True, padx=10)
            stat_card.pack_propagate(False)
        
            CTkLabel(stat_card, text=title, font=("Arial", 12, "bold")).pack(pady=(15, 5))
            CTkLabel(stat_card, text=str(value), font=("Arial", 18, "bold"), 
                     text_color=color).pack(pady=5)
        
        actions_frame = CTkFrame(content)
        actions_frame.pack(fill="x", pady=20)
        
        CTkLabel(actions_frame, text="Ações Rápidas:", 
                 font=("Arial", 16, "bold")).pack(pady=10)
        
        # Ações Rápidas com Tooltips
        quick_actions_info = [
            # Botão modificado para abrir a aba Cartelas para configuração
            (f"Gerar Cartelas ({self.total_cartelas} / Max {self.numero_maximo})", self.show_cartelas, "Define e Gera o número de cartelas e o número máximo de sorteio."), 
            ("Novo Comprador", lambda: self.show_compradores(), "Abre a aba para cadastrar novos compradores."),
            ("Sortear Número", self.sortear_numero, "Sorteia o próximo número automaticamente."),
            ("Exportar Relatórios", self.exportar_excel, "Exporta todos os dados (cartelas e compradores) para Excel."),
            ("🔄 Novo Concurso", self.novo_concurso_dialog, "Salva o concurso atual e inicia um novo sistema limpo.")
        ]
        
        btn_frame = CTkFrame(actions_frame)
        btn_frame.pack(pady=10)

        # Botão de Ajuda
        btn_ajuda = CTkButton(btn_frame, text="❓ Ajuda/Fluxo", 
                              command=self.mostrar_ajuda_fluxo,
                              fg_color="#2196F3", hover_color="#1976D2",
                              width=150, height=35)
        btn_ajuda.pack(side="left", padx=5, pady=5)
        self.add_tooltip_and_status(btn_ajuda, "Exibe a ordem de trabalho recomendada para o sistema.")
        
        
        for text, command, tooltip_text in quick_actions_info:
            btn = CTkButton(btn_frame, text=text, command=command,
                            width=150, height=35)
            btn.pack(side="left", padx=5, pady=5)
            self.add_tooltip_and_status(btn, tooltip_text)
            
            # Controle de estado: Desabilita tudo exceto Gerar Cartelas e Novo Concurso
            state = "normal"
            # [MODIFICADO] Restringe o botão 'Gerar Cartelas' após a primeira vez
            if text.startswith("Gerar Cartelas") and self.cartelas_geradas_uma_vez:
                btn.configure(text="Cartelas Geradas (Bloqueado)", state="disabled", fg_color="#F44336", hover_color="#d32f2f")
                continue
            
            if not text.startswith("Gerar Cartelas") and text not in ["🔄 Novo Concurso"] and not self.cartelas_geradas:
                 state = "disabled"

            btn.configure(state=state)


    def mostrar_ajuda_fluxo(self):
        """Exibe a janela com o fluxo de trabalho recomendado."""
        help_text = (
            "🚀 FLUXO DE TRABALHO RECOMENDADO:\n\n"
            "1. **CONFIGURAR E GERAR CARTELAS** (Aba Cartelas)\n" # [MODIFICADO]
            "   - Essencial! Define a base de cartelas e o máximo de números (ex: 90).\n"
            "   - *Esta ação só pode ser feita UMA VEZ por concurso.* \n\n" 
            "2. **EXPORTAR PDF** (Aba Cartelas)\n"
            "   - Gere o PDF para impressão na gráfica.\n\n"
            "3. **CADASTRAR COMPRADORES** (Aba Compradores)\n"
            "   - Atribua as cartelas vendidas aos seus respectivos compradores.\n\n"
            "4. **REALIZAR SORTEIO** (Aba Sorteio)\n"
            "   - Comece a sortear os números (automático ou manual).\n\n"
            "5. **VERIFICAR VENCEDOR** (Aba Sorteio)\n"
            "   - Confirme o vencedor ao final do sorteio.\n\n"
            "6. **SALVAR CONCURSO / BACKUP** (Aba Concursos)\n" 
            "   - Salve o estado atual para consulta futura ou crie um backup externo."
        )

        janela = ctk.CTkToplevel(self.root)
        janela.title("Ajuda - Fluxo de Trabalho")
        janela.geometry("500x480") 
        janela.transient(self.root)
        janela.grab_set()

        CTkLabel(janela, text="Ordem de Tarefas Recomendada", 
                 font=("Arial", 18, "bold")).pack(pady=10)
        
        textbox_ajuda = CTkTextbox(janela, height=330, width=450, wrap="word")
        textbox_ajuda.insert("1.0", help_text)
        textbox_ajuda.configure(state="disabled") # Desabilita edição
        textbox_ajuda.pack(padx=10, pady=10)
        
        CTkButton(janela, text="Entendi", command=janela.destroy).pack(pady=10)
        
    def show_compradores(self):
        # ... (Mantido, com ajuste no placeholder do número máximo)
        self.clear_content_frame()
        self.highlight_tab(1)
        
        content = CTkScrollableFrame(self.content_frame)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        CTkLabel(content, text="Cadastro e Gestão de Compradores",  # Título atualizado
                 font=("Arial", 18, "bold")).pack(pady=10)
        
        form_frame = CTkFrame(content)
        form_frame.pack(fill="x", pady=10)
        
        campos = [
            ("Nome Completo:", "entry_nome"),
            ("Endereço:", "entry_endereco"), 
            ("Celular:", "entry_celular"),
            ("Vendedor:", "entry_vendedor"),
            ("Quantidade de Cartelas:", "entry_quantidade")
        ]
        
        self.entries = {}
        for label, key in campos:
            row = CTkFrame(form_frame)
            row.pack(fill="x", pady=8, padx=20)
            
            CTkLabel(row, text=label, width=150, anchor="w").pack(side="left")
            if key == "entry_quantidade":
                entry = CTkEntry(row, placeholder_text="1", width=100)
                entry.pack(side="left", padx=10)
                entry.insert(0, "1")
            else:
                entry = CTkEntry(row, placeholder_text=f"Digite o {label.lower().replace(':', '')}")
                entry.pack(side="left", fill="x", expand=True, padx=10)
            self.entries[key] = entry
        
        cartelas_frame = CTkFrame(form_frame)
        cartelas_frame.pack(fill="x", pady=8, padx=20)
        
        CTkLabel(cartelas_frame, text="Cartelas para Atribuir:", width=150, anchor="w").pack(side="left")
        
        self.cartelas_selecionadas_var = tk.StringVar()
        cartelas_entry = CTkEntry(cartelas_frame, textvariable=self.cartelas_selecionadas_var,
                                 placeholder_text="Ex: 1,2,3 ou 1-5 (Vazio para automático)")
        cartelas_entry.pack(side="left", fill="x", expand=True, padx=10)
        
        btn_disp = CTkButton(cartelas_frame, text="📋 Ver Disponíveis", 
                             command=self.mostrar_cartelas_disponiveis, width=120)
        btn_disp.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_disp, "Lista as IDs das cartelas que ainda não foram vendidas.")
        
        btn_frame = CTkFrame(form_frame)
        btn_frame.pack(fill="x", pady=15, padx=20)
        
        btn_cadastrar = CTkButton(btn_frame, text="📝 Cadastrar Comprador", 
                                  command=self.cadastrar_comprador, 
                                  fg_color="#4CAF50", hover_color="#45a049")
        btn_cadastrar.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_cadastrar, "Salva o comprador e atribui as cartelas indicadas.")

        btn_limpar = CTkButton(btn_frame, text="🔄 Limpar Campos", 
                                  command=self.limpar_campos)
        btn_limpar.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_limpar, "Limpa todos os campos do formulário.")
        
        # NOVO BOTÃO DE AÇÃO
        btn_desvincular = CTkButton(btn_frame, text="🚫 Desvincular Cartela", 
                                  command=self.desvincular_cartela,
                                  fg_color="#F44336", hover_color="#d32f2f") # Adicionado
        btn_desvincular.pack(side="right", padx=5) 
        self.add_tooltip_and_status(btn_desvincular, "Desvincula uma cartela vendida, tornando-a livre novamente.")

        # Controles de estado para esta aba
        state = "normal" if self.cartelas_geradas else "disabled"
        for widget in [btn_disp, btn_cadastrar, btn_limpar, btn_desvincular]:
            widget.configure(state=state)
        for entry in self.entries.values():
            entry.configure(state=state)
        cartelas_entry.configure(state=state)
        
        CTkLabel(content, text="Compradores Cadastrados", 
                 font=("Arial", 16, "bold")).pack(pady=(20, 10))
        
        self.compradores_text = CTkTextbox(content, height=200)
        self.compradores_text.pack(fill="both", expand=True, pady=10)
        
        self.atualizar_lista_compradores()

    def show_cartelas(self):
        self.clear_content_frame()
        self.highlight_tab(2)
        
        content = CTkFrame(self.content_frame)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        CTkLabel(content, text="Gerenciamento e Geração de Cartelas (Versão Plus)", # [MODIFICADO]
                 font=("Arial", 18, "bold")).pack(pady=10)
        
        # --- NOVO: FRAME DE CONFIGURAÇÃO DE GERAÇÃO ---
        config_frame = CTkFrame(content)
        config_frame.pack(fill="x", pady=10)
        
        CTkLabel(config_frame, text="Configurações de Geração:", font=("Arial", 14, "bold")).pack(pady=(5, 0))
        
        input_frame = CTkFrame(config_frame)
        input_frame.pack(pady=10, padx=10, fill="x")

        # 1. Campo para definir quantas cartelas deseja gerar [NOVO]
        CTkLabel(input_frame, text="Total de Cartelas a Gerar:", width=180, anchor="w").pack(side="left", padx=(10, 5))
        self.entry_total_cartelas = CTkEntry(input_frame, placeholder_text=str(DEFAULT_TOTAL_CARTELAS), width=100)
        self.entry_total_cartelas.pack(side="left", padx=(0, 20))
        self.entry_total_cartelas.insert(0, str(self.total_cartelas))
        ToolTip(self.entry_total_cartelas, "Defina quantas cartelas únicas o programa deve tentar gerar (Ex: 50, 100, 126).")
        
        # 2. Campo para definir quantos números serão sorteados (o máximo) [NOVO]
        CTkLabel(input_frame, text="Número Máximo do Sorteio (BINGO):", width=250, anchor="w").pack(side="left", padx=(10, 5))
        self.entry_num_max = CTkEntry(input_frame, placeholder_text=str(DEFAULT_NUMERO_MAXIMO), width=100)
        self.entry_num_max.pack(side="left", padx=(0, 10))
        self.entry_num_max.insert(0, str(self.numero_maximo))
        ToolTip(self.entry_num_max, "Defina o número máximo do sorteio (Ex: 75, 90). As cartelas serão geradas com 25 números nesse range.")
        
        # -----------------------------------------------------

        controls_frame = CTkFrame(content)
        controls_frame.pack(fill="x", pady=10)
        
        # Botão de Geração agora chama um novo método de validação
        btn_gerar = CTkButton(controls_frame, text="🎫 GERAR CARTELAS ÚNICAS", 
                              command=self.validar_e_gerar_cartelas, # [MODIFICADO]
                              fg_color="#4CAF50", hover_color="#45a049",
                              width=250, height=40)
        btn_gerar.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_gerar, "Define as configurações e gera as cartelas únicas, limpando as antigas.")

        btn_pdf = CTkButton(controls_frame, text="📄 Exportar PDF (Gráfica)", 
                            command=self.exportar_pdf)
        btn_pdf.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_pdf, "Cria um PDF pronto para impressão (sem marcações).")

        btn_excel = CTkButton(controls_frame, text="📊 Exportar Excel", 
                              command=self.exportar_excel)
        btn_excel.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_excel, "Exporta cartelas, compradores e sorteio para um arquivo Excel.")

        btn_visualizar = CTkButton(controls_frame, text="👁 Visualizar Cartela", 
                                   command=self.visualizar_cartela)
        btn_visualizar.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_visualizar, "Busca e exibe o estado de uma cartela específica.")
        
        # Controle de estado para esta aba
        state = "normal" if self.cartelas_geradas else "disabled"
        for widget in [btn_pdf, btn_excel, btn_visualizar]:
            widget.configure(state=state)

        # [MODIFICADO] Restringe o botão 'Gerar Cartelas' após a primeira vez
        if self.cartelas_geradas_uma_vez:
            btn_gerar.configure(text="Cartelas Geradas (Bloqueado)", state="disabled", fg_color="#F44336", hover_color="#d32f2f")
            # Desabilita as entries de configuração se já gerado
            self.entry_total_cartelas.configure(state="disabled")
            self.entry_num_max.configure(state="disabled")
        else:
            btn_gerar.configure(state="normal")
            self.entry_total_cartelas.configure(state="normal")
            self.entry_num_max.configure(state="normal")
        
        info_frame = CTkFrame(content)
        info_frame.pack(fill="both", expand=True, pady=10)
        
        self.cartelas_text = CTkTextbox(info_frame, wrap="word")
        self.cartelas_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.atualizar_info_cartelas()

    def show_sorteio(self):
        # ... (Mantido, com ajuste no placeholder)
        self.clear_content_frame()
        self.highlight_tab(3)
        
        content = CTkFrame(self.content_frame)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        CTkLabel(content, text="Controle de Sorteio", 
                 font=("Arial", 18, "bold")).pack(pady=10)
        
        main_sorteio_frame = CTkFrame(content)
        main_sorteio_frame.pack(fill="both", expand=True, pady=10)
        
        left_frame = CTkFrame(main_sorteio_frame, width=400)
        left_frame.pack(side="left", fill="y", padx=10, pady=10)
        left_frame.pack_propagate(False)
        
        numero_frame = CTkFrame(left_frame, height=150)
        numero_frame.pack(fill="x", pady=10, padx=10)
        numero_frame.pack_propagate(False)
        
        CTkLabel(numero_frame, text="Último Número Sorteado", 
                 font=("Arial", 14)).pack(pady=(10, 0))
        
        self.numero_display = CTkLabel(numero_frame, text="--", 
                                             font=("Arial", 48, "bold"),
                                             text_color="#FF5722")
        self.numero_display.pack(pady=10)
        self.atualizar_display_numero()
        
        btn_frame = CTkFrame(left_frame)
        btn_frame.pack(fill="x", pady=5, padx=10)
        
        # Botões de Sorteio
        btn_sortear = CTkButton(btn_frame, text="🎲 Sortear Automaticamente", 
                                command=self.sortear_numero,
                                fg_color="#FF9800", hover_color="#F57C00",
                                height=40)
        btn_sortear.pack(fill="x", padx=5, pady=5)
        self.add_tooltip_and_status(btn_sortear, f"Sorteia um número de 1 a {self.numero_maximo} que ainda não saiu.") # [MODIFICADO]
        
        manual_frame = CTkFrame(left_frame)
        manual_frame.pack(fill="x", pady=10, padx=10)
        
        self.entry_numero_manual = CTkEntry(manual_frame, placeholder_text=f"Número (1-{self.numero_maximo})", width=100) # [MODIFICADO]
        self.entry_numero_manual.pack(side="left", fill="x", expand=True, padx=5)
        
        btn_manual = CTkButton(manual_frame, text="📝 Inserir Manual", 
                               command=self.inserir_numero_manual, width=120)
        btn_manual.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_manual, "Insere um número manualmente no sorteio.")
                
        controles_frame_2 = CTkFrame(left_frame)
        controles_frame_2.pack(fill="x", pady=10, padx=10)

        btn_verificar = CTkButton(controles_frame_2, text="✅ Verificar Vencedor", 
                                  command=self.verificar_vencedor,
                                  fg_color="#4CAF50", hover_color="#45a049", width=120)
        btn_verificar.pack(side="left", padx=5, pady=5)
        self.add_tooltip_and_status(btn_verificar, "Verifica se há cartelas com 25 acertos (BINGO).")
        
        btn_reiniciar = CTkButton(controles_frame_2, text="🔄 Reiniciar Sorteio", 
                                  command=self.reiniciar_sorteio,
                                  fg_color="#F44336", hover_color="#d32f2f", width=120)
        btn_reiniciar.pack(side="right", padx=5, pady=5)
        self.add_tooltip_and_status(btn_reiniciar, "Zera todos os números sorteados e acertos das cartelas.")
        
        # Controle de estado para esta aba
        state = "normal" if self.cartelas_geradas else "disabled"
        for widget in [btn_sortear, btn_manual, btn_verificar, btn_reiniciar, self.entry_numero_manual]:
            widget.configure(state=state)

        right_frame = CTkFrame(main_sorteio_frame)
        right_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        # Top 20 (Agora Horizontal)
        CTkLabel(right_frame, text="🔥 Top 20 Cartelas (Mais Acertos) - ID (Acertos)", 
                 font=("Arial", 14, "bold")).pack(pady=(0, 5))
        
        self.top20_scroll_frame = CTkScrollableFrame(right_frame, height=180, orientation="horizontal")
        self.top20_scroll_frame.pack(fill="x", padx=5, pady=(0, 10))
        
        self.top20_container_frame = CTkFrame(self.top20_scroll_frame, fg_color="transparent")
        self.top20_container_frame.pack(fill="y", expand=True)
        self.mostrar_top20_no_sorteio()
        
        # Histórico Completo de Sorteios (Agora Horizontal)
        CTkLabel(right_frame, text=f"🔢 Histórico Completo de Sorteios (1-{self.numero_maximo})", # [MODIFICADO]
                 font=("Arial", 14, "bold")).pack(pady=(10, 5))
        
        self.historico_scroll_frame = CTkScrollableFrame(right_frame, height=150, orientation="horizontal")
        self.historico_scroll_frame.pack(fill="x", expand=True, padx=5, pady=5)

        self.historico_container_frame = CTkFrame(self.historico_scroll_frame, fg_color="transparent")
        self.historico_container_frame.pack(fill="y", expand=True)

        self.atualizar_historico()

    def show_relatorios(self):
        # ... (Mantido)
        self.clear_content_frame()
        self.highlight_tab(4)
        
        content = CTkFrame(self.content_frame)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        CTkLabel(content, text="Relatórios e Estatísticas", 
                 font=("Arial", 18, "bold")).pack(pady=10)
        
        reports_frame = CTkFrame(content)
        reports_frame.pack(fill="x", pady=10)
        
        reports_info = [
            ("🏆 Top 20 Cartelas", self.mostrar_top20, "Exibe as 20 cartelas com mais acertos."),
            ("🎯 Cartela Vencedora", self.mostrar_vencedor, "Exibe os dados da cartela e comprador premiados."),
            ("👥 Listar Compradores", self.listar_compradores, "Lista completa de compradores e suas informações."),
            ("📈 Estatísticas Completas", self.mostrar_estatisticas, "Exibe dados de vendas, acertos e números sorteados."),
            ("📋 Cartelas por Comprador", self.mostrar_cartelas_comprador, "Busca e lista todas as cartelas de um comprador específico.")
        ]
        
        for text, command, tooltip_text in reports_info:
            btn = CTkButton(reports_frame, text=text, command=command,
                            width=180, height=35)
            btn.pack(side="left", padx=5, pady=5)
            self.add_tooltip_and_status(btn, tooltip_text)
            
            # Controle de estado
            btn.configure(state="normal" if self.cartelas_geradas else "disabled")
        
        self.relatorios_text = CTkTextbox(content)
        self.relatorios_text.pack(fill="both", expand=True, pady=10)
        
    def show_concursos(self):
        # ... (Mantido)
        self.clear_content_frame()
        self.highlight_tab(5)
        
        content = CTkFrame(self.content_frame)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        CTkLabel(content, text="Gerenciamento de Concursos e Backup", # [MODIFICADO]
                 font=("Arial", 18, "bold")).pack(pady=10)
        
        controls_frame_concursos = CTkFrame(content)
        controls_frame_concursos.pack(fill="x", pady=10)

        # Botões de Concursos com Tooltips
        btn_novo = CTkButton(controls_frame_concursos, text="➕ Novo Concurso", command=self.novo_concurso_dialog,
                             fg_color="#4CAF50", hover_color="#45a049")
        btn_novo.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_novo, "Inicia um novo concurso limpo, salvando o atual (opcional).")

        btn_salvar = CTkButton(controls_frame_concursos, text="💾 Salvar Concurso Atual", command=self.salvar_concurso_atual)
        btn_salvar.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_salvar, "Salva o estado atual do sistema para uso posterior.")

        btn_carregar = CTkButton(controls_frame_concursos, text="📂 Carregar Concurso", command=self.carregar_concurso_dialog)
        btn_carregar.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_carregar, "Carrega um concurso salvo, substituindo o atual.")

        btn_excluir = CTkButton(controls_frame_concursos, text="🗑️ Excluir Concurso", command=self.excluir_concurso_dialog,
                                  fg_color="#F44336", hover_color="#d32f2f")
        btn_excluir.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_excluir, "Exclui permanentemente um concurso salvo (com confirmação).")

        # [ADICIONADO] Botões de Backup
        controls_frame_backup = CTkFrame(content)
        controls_frame_backup.pack(fill="x", pady=10)
        
        CTkLabel(controls_frame_backup, text="Ferramentas de Backup:", font=("Arial", 14, "bold")).pack(side="left", padx=5)

        btn_backup = CTkButton(controls_frame_backup, text="📦 Criar Backup (.json)", command=self.criar_backup,
                              fg_color="#FF9800", hover_color="#F57C00")
        btn_backup.pack(side="left", padx=10)
        self.add_tooltip_and_status(btn_backup, "Salva um arquivo de backup completo em um local escolhido por você.")

        btn_restaurar = CTkButton(controls_frame_backup, text="↩️ Restaurar Backup", command=self.restaurar_backup)
        btn_restaurar.pack(side="left", padx=5)
        self.add_tooltip_and_status(btn_restaurar, "Carrega dados de um arquivo de backup, sobrescrevendo o concurso atual.")

        btn_limpar_tudo = CTkButton(controls_frame_backup, text="💣 Limpar Tudo", command=self.limpar_tudo_definitivo,
                                  fg_color="#8B0000", hover_color="#B22222") # Botão de Reset Completo
        btn_limpar_tudo.pack(side="right", padx=5)
        self.add_tooltip_and_status(btn_limpar_tudo, "RESSETA o sistema por completo (perda total de dados).")

        list_frame = CTkFrame(content)
        list_frame.pack(fill="both", expand=True, pady=10)

        CTkLabel(list_frame, text="Concursos Salvos", font=("Arial", 14, "bold")).pack(pady=(10, 5))
        self.concursos_list = CTkTextbox(list_frame, height=200)
        self.concursos_list.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.atualizar_lista_concursos()

    # --- Métodos de Cartelas (MODIFICADOS) ---
    
    # [NOVO] Método de validação antes da geração
    def validar_e_gerar_cartelas(self):
        if self.cartelas_geradas_uma_vez:
            messagebox.showwarning("Ação Bloqueada", 
                                   "⚠️ A geração de cartelas só pode ser realizada UMA VEZ por concurso.\n"
                                   "Para gerar novas cartelas, inicie um **Novo Concurso** (Aba Concursos).")
            return
            
        try:
            total_cartelas = int(self.entry_total_cartelas.get())
            numero_maximo = int(self.entry_num_max.get())
        except ValueError:
            messagebox.showerror("Erro de Entrada", "❌ Os campos de Total de Cartelas e Número Máximo devem ser números inteiros.")
            return

        if total_cartelas < 1:
            messagebox.showerror("Erro de Geração", "❌ O total de cartelas deve ser no mínimo 1.")
            return
        
        # A cartela de Bingo padrão tem 25 números.
        if numero_maximo < 25:
             messagebox.showerror("Erro de Geração", "❌ O número máximo do sorteio deve ser no mínimo 25 (para permitir a criação da cartela padrão de 25 números).")
             return
             
        # Atualiza as variáveis de configuração
        self.total_cartelas = total_cartelas
        self.numero_maximo = numero_maximo
        
        # Inicia a geração em thread
        self.gerar_cartelas_com_loading()
        
    def gerar_cartela(self):
        # Alterado o range para 1 a self.numero_maximo [MODIFICADO]
        return sorted(random.sample(range(1, self.numero_maximo + 1), 25))

    def gerar_cartelas_com_loading(self):
        # [MODIFICADO] Restrição de geração
        if self.cartelas_geradas_uma_vez:
            # Já validado no método 'validar_e_gerar_cartelas', mas mantido por segurança
            return 

        if self.cartelas and not messagebox.askyesno("Confirmar Ação", 
                                                  "⚠️ Isso irá substituir as cartelas existentes.\nDeseja continuar?"):
            log_message("INFO", "Geração de cartelas cancelada pelo usuário.")
            return
            
        loading = LoadingWindow(self.root, f"Gerando {self.total_cartelas} Cartelas Únicas...") # [MODIFICADO]
        log_message("INFO", f"Iniciando geração de {self.total_cartelas} cartelas únicas em thread (Max: {self.numero_maximo}).") # [MODIFICADO]

        def gerar_em_thread():
            try:
                # 🛡️ Proteção e Limpeza: Zera dados antigos de vendas/sorteio
                self.cartelas = {}
                self.compradores = {} # Limpa compradores também, pois as cartelas mudaram
                self.numeros_sorteados = set()
                self.historico_sorteios = []
                self.ultimo_numero_sorteado = None
                self.cartela_vencedora = None 
                
                cartelas_geradas_sets = set()
                total_cartelas = self.total_cartelas # [MODIFICADO]
                i = 1
                
                # Definindo um limite razoável de iterações para evitar loops muito longos 
                # (ex: 5000 iterações para 126 cartelas é mais do que o suficiente)
                limite_iteracoes = total_cartelas * 20 
                iteracoes = 0
                
                while i <= total_cartelas:
                    iteracoes += 1
                    if iteracoes > limite_iteracoes:
                        log_message("ERROR", f"Loop de geração atingiu limite de {limite_iteracoes} iterações. Cartelas geradas: {i-1}.")
                        break

                    nova_cartela = self.gerar_cartela()
                    nova_cartela_tuple = tuple(nova_cartela)
                    
                    if nova_cartela_tuple not in cartelas_geradas_sets:
                        cartela_id = str(i)
                        
                        self.cartelas[cartela_id] = {
                            'numeros': nova_cartela,
                            'acertos': 0,
                            'comprador_id': None,
                            'data_criacao': datetime.now().strftime("%d/%m/%Y %H:%M")
                        }
                
                        cartelas_geradas_sets.add(nova_cartela_tuple)
                        
                        i += 1
                        
                        progress = i / (total_cartelas + 1)
                        status = f"Cartela {i-1}/{total_cartelas} gerada..."
                        self.root.after(0, lambda p=progress, s=status: loading.update_progress(p, s))

                self.root.after(0, lambda: loading.update_progress(1.0, "Salvando dados..."))
                self.save_data()
                self.cartelas_geradas = True 
                self.cartelas_geradas_uma_vez = True # [ADICIONADO] Define a flag como True após a geração
                
                cartelas_efetivamente_geradas = len(self.cartelas)
                
                self.root.after(0, lambda: [
                    loading.close(),
                    self.atualizar_status(),
                    self.atualizar_info_cartelas(),
                    self.mostrar_top20_no_sorteio(),
                    self.update_ui_state(), 
                    log_message("SUCCESS", f"{cartelas_efetivamente_geradas} cartelas geradas. Botões dependentes habilitados. Vencedor não pré-definido."),
                    messagebox.showinfo("Sucesso", 
                                        f"🎉 {cartelas_efetivamente_geradas} cartelas **únicas** geradas com sucesso!\n"
                                        f"Número Máximo do Sorteio: {self.numero_maximo}\n"
                                        f"O sistema agora está pronto para cadastrar compradores e iniciar o sorteio."),
                    # [ADICIONADO] Solicita salvamento do concurso após a 1ª geração
                    self.solicitar_salvamento_apos_geracao() 
                ])
            
            except Exception as e:
                log_message("ERROR", f"Erro fatal ao gerar cartelas: {str(e)}")
                self.root.after(0, lambda: [
                    loading.close(),
                    messagebox.showerror("Erro", f"❌ Erro ao gerar cartelas: {str(e)}")
                ])
        
        threading.Thread(target=gerar_em_thread, daemon=True).start()

    def solicitar_salvamento_apos_geracao(self):
        """Solicita o salvamento automático do concurso após a primeira geração de cartelas."""
        if messagebox.askyesno("Salvar Concurso", 
                               "⚠️ Cartelas geradas! É essencial salvar o concurso para que a base de cartelas seja permanente.\n"
                               f"Deseja salvar o concurso '{self.concurso_atual}' agora?"):
            self.salvar_concurso_atual() # Chama a função de salvar
            self.show_home() # Volta para a home

    def atualizar_info_cartelas(self):
        # ... (Mantido, com atualização no texto)
        if not hasattr(self, 'cartelas_text') or not self.cartelas_text.winfo_exists(): return
        
        try:
            self.cartelas_text.delete("1.0", "end")
                
            if not self.cartelas:
                # [MODIFICADO] Mensagem para refletir o estado de geração única
                if self.cartelas_geradas_uma_vez:
                    self.cartelas_text.insert("end", "⚠️ Nenhuma cartela atual. Inicie um Novo Concurso para gerar novamente.")
                else:
                    self.cartelas_text.insert("end", "⚠️ Nenhuma cartela gerada! Configure o **Total de Cartelas** e o **Número Máximo** acima e clique em **GERAR CARTELAS ÚNICAS**.")
                return
                
            cartelas_livres = sum(1 for c in self.cartelas.values() if not c.get('comprador_id'))
            vendidas = len(self.cartelas) - cartelas_livres
            
            # Atualiza a exibição da cartela vencedora
            vencedora_info = self.cartela_vencedora if self.cartela_vencedora else "Aguardando Sorteio"

            self.cartelas_text.insert("end", f"ESTATÍSTICAS ATUAIS (Máximo Sorteio: {self.numero_maximo}):\n") # [MODIFICADO]
            self.cartelas_text.insert("end", f"Total de Cartelas Geradas: {len(self.cartelas)}\n") # [MODIFICADO]
            self.cartelas_text.insert("end", f"Vendidas: {vendidas} | Livres: {cartelas_livres}\n")
            self.cartelas_text.insert("end", f"Cartela Vencedora: {vencedora_info}\n\n")
            
            self.cartelas_text.insert("end", "LISTA (ID: [Números]):\n")
            
            cartela_ids = sorted(self.cartelas.keys(), key=lambda x: int(x))
            for cartela_id in cartela_ids:
                cartela = self.cartelas[cartela_id]
                numeros_str = ', '.join(map(str, cartela['numeros']))
                comprador_status = "Livre"
                if cartela.get('comprador_id'):
                    nome = self.compradores.get(cartela['comprador_id'], {}).get('nome', 'Desconhecido')
                    comprador_status = f"VENDIDA para {nome}"
                
                self.cartelas_text.insert("end", f"ID {cartela_id.zfill(3)} ({comprador_status}): [{numeros_str}]\n")
        except Exception as e:
            log_message("ERROR", f"Erro ao atualizar info de cartelas: {e}")


    def mostrar_cartelas_disponiveis(self):
        # ... (Mantido)
        if not self.cartelas:
            messagebox.showwarning("Atenção", "⚠️ Nenhuma cartela gerada!")
            return
        
        log_message("INFO", "Exibindo cartelas disponíveis.")
        cartelas_disponiveis = [cid for cid, cartela in self.cartelas.items() if not cartela.get('comprador_id')]
        
        if not cartelas_disponiveis:
            messagebox.showinfo("Info", "❌ Todas as cartelas já foram atribuídas!")
            return
        
        janela = ctk.CTkToplevel(self.root)
        janela.title("Cartelas Disponíveis")
        janela.geometry("400x300")
        
        CTkLabel(janela, text="Cartelas Disponíveis para Atribuição", 
                 font=("Arial", 16, "bold")).pack(pady=10)
        
        texto = CTkTextbox(janela)
        texto.pack(fill="both", expand=True, padx=10, pady=10)
        
        cartelas_numeros = sorted([int(cid) for cid in cartelas_disponiveis])
        intervalos = []
        if cartelas_numeros:
            inicio = cartelas_numeros[0]
            
            for i in range(1, len(cartelas_numeros)):
                if cartelas_numeros[i] != cartelas_numeros[i-1] + 1:
                    if inicio == cartelas_numeros[i-1]:
                        intervalos.append(str(inicio))
                    else:
                        intervalos.append(f"{inicio}-{cartelas_numeros[i-1]}")
                    inicio = cartelas_numeros[i]
            
            if inicio == cartelas_numeros[-1]:
                intervalos.append(str(inicio))
            else:
                intervalos.append(f"{inicio}-{cartelas_numeros[-1]}")
        
        texto.insert("1.0", "Disponíveis: " + ", ".join(intervalos))
        texto.configure(state="disabled")

    # --- Métodos de Compradores (Mantidos) ---
    
    def cadastrar_comprador(self):
        # ... (Mantido)
        if not self.cartelas_geradas:
            messagebox.showwarning("Atenção", "⚠️ Gere as cartelas primeiro!")
            return

        try:
            nome = self.entries['entry_nome'].get().strip()
            endereco = self.entries['entry_endereco'].get().strip()
            celular = self.entries['entry_celular'].get().strip()
            vendedor = self.entries['entry_vendedor'].get().strip()
            quantidade_text = self.entries['entry_quantidade'].get().strip()
            cartelas_selecionadas = self.cartelas_selecionadas_var.get().strip()
            
            if not all([nome, celular]):
                messagebox.showwarning("Atenção", "⚠️ Campos obrigatórios: Nome e Celular!")
                return
            
            try:
                quantidade = int(quantidade_text) if quantidade_text.isdigit() else 1
                if quantidade < 1: quantidade = 1
            except:
                quantidade = 1
            
            comprador_id = str(len(self.compradores) + 1).zfill(3)
            cartelas_atribuidas = []
            
            # --- LÓGICA DE ATRIBUIÇÃO ---
            if cartelas_selecionadas:
                if '-' in cartelas_selecionadas:
                    try:
                        inicio, fim = map(int, cartelas_selecionadas.split('-'))
                        cartelas_atribuidas = [str(i) for i in range(inicio, fim + 1)]
                    except ValueError:
                        messagebox.showerror("Erro", f"❌ Formato de intervalo inválido. Use N-N (Ex: 1-5)")
                        return
                else:
                    cartelas_atribuidas = [c.strip() for c in cartelas_selecionadas.split(',') if c.strip() and c.strip().isdigit()]
                
                # Validação de IDs e disponibilidade
                for cartela_id in cartelas_atribuidas:
                    if cartela_id not in self.cartelas:
                        messagebox.showerror("Erro", f"❌ Cartela {cartela_id} não existe!")
                        return
                    if self.cartelas[cartela_id].get('comprador_id'):
                        comprador_existente = self.compradores.get(self.cartelas[cartela_id]['comprador_id'], {}).get('nome', 'Outro Comprador')
                        messagebox.showerror("Erro", f"❌ Cartela {cartela_id} já está atribuída para: {comprador_existente}!")
                        return
            else:
                # Atribuição automática (por quantidade)
                cartelas_disponiveis = [cid for cid, cartela in self.cartelas.items() 
                                        if not cartela.get('comprador_id')]
                
                if len(cartelas_disponiveis) < quantidade:
                    messagebox.showerror("Erro", 
                                         f"❌ Não há cartelas suficientes!\n"
                                         f"Disponíveis: {len(cartelas_disponiveis)}\n"
                                         f"Solicitadas: {quantidade}")
                    return
                
                cartelas_atribuidas = sorted(cartelas_disponiveis, key=int)[:quantidade]
            
            if not cartelas_atribuidas:
                messagebox.showwarning("Atenção", "Nenhuma cartela foi atribuída. Verifique a quantidade ou as IDs.")
                return

            # Criação do Comprador
            self.compradores[comprador_id] = {
                'nome': nome,
                'endereco': endereco,
                'celular': celular,
                'vendedor': vendedor,
                'data_cadastro': datetime.now().strftime("%d/%m/%Y %H:%M"),
                'cartelas': cartelas_atribuidas
            }
            
            # Atribuição nas Cartelas
            for cartela_id in cartelas_atribuidas:
                self.cartelas[cartela_id]['comprador_id'] = comprador_id
            
            self.save_data()
            
            # 🐞 CORREÇÃO DO ERRO: Adia as chamadas para prevenir "invalid command name"
            self.root.after(100, self.atualizar_status)
            self.root.after(100, self.atualizar_lista_compradores)
            self.root.after(100, self.atualizar_info_cartelas)
            
            self.limpar_campos() 
            
            log_message("SUCCESS", f"Comprador ID {comprador_id} ('{nome}') cadastrado com {len(cartelas_atribuidas)} cartelas.")
            messagebox.showinfo("Sucesso", 
                                 f"✅ Comprador cadastrado e salvo com sucesso!\n"
                                 f"📋 ID: {comprador_id}\n"
                                 f"👤 Nome: {nome}\n"
                                 f"🎫 Cartelas atribuídas: {len(cartelas_atribuidas)}")
            
        except Exception as e:
            log_message("ERROR", f"Erro ao cadastrar comprador: {str(e)}")
            messagebox.showerror("Erro ao cadastrar comprador", f"Erro: {str(e)}")

    
    def limpar_campos(self):
        # ... (Mantido)
        if not hasattr(self, 'entries'): return
        
        try:
            for key, entry in self.entries.items():
                entry.delete(0, 'end')
            
            if 'entry_quantidade' in self.entries:
                self.entries['entry_quantidade'].insert(0, "1")
            
            if hasattr(self, 'cartelas_selecionadas_var'):
                 self.cartelas_selecionadas_var.set("")
                 
        except Exception as e:
            # print(f"Erro ignorado ao tentar limpar campos: {e}")
            pass

    def atualizar_lista_compradores(self):
        # ... (Mantido)
        if not hasattr(self, 'compradores_text') or not self.compradores_text.winfo_exists(): 
            return
        
        self.compradores_text.delete("1.0", "end")
        
        if not self.compradores:
            self.compradores_text.insert("end", "⚠️ Ninguém cadastrado ainda.")
            return
            
        self.compradores_text.insert("end", "ID | Nome (Vendedor) | Celular | Cartelas\n")
        self.compradores_text.insert("end", "───┼─────────────────┼─────────┼──────────\n")
        
        comprador_ids = sorted(self.compradores.keys(), key=lambda x: int(x))
        for cid in comprador_ids:
            comprador = self.compradores[cid]
            cartelas_str = ', '.join(comprador['cartelas'])
            
            linha = (f"{cid.zfill(3)} | "
                     f"{comprador['nome']} ({comprador['vendedor']}) | "
                     f"{comprador['celular']} | "
                     f"{len(comprador['cartelas'])} ({cartelas_str[:50]}...)\n")
            self.compradores_text.insert("end", linha)

    # --- MÉTODO DE DESVINCULAÇÃO DE CARTELA (Mantido) ---
    
    def desvincular_cartela(self):
        # ... (Mantido)
        """Desvincula uma cartela específica do comprador atribuído, tornando-a livre."""
        if not self.cartelas:
            messagebox.showwarning("Atenção", "⚠️ Nenhuma cartela gerada!")
            return

        cartela_id = simpledialog.askstring("Desvincular Cartela", "Digite o ID da Cartela para desvincular:")
        if not cartela_id or not cartela_id.isdigit(): 
             if cartela_id: messagebox.showwarning("Atenção", "ID da cartela inválido.")
             return

        if cartela_id not in self.cartelas:
            messagebox.showerror("Erro", f"❌ Cartela ID {cartela_id} não existe!")
            return

        cartela = self.cartelas[cartela_id]
        comprador_id = cartela.get('comprador_id')

        if not comprador_id:
            messagebox.showwarning("Atenção", f"⚠️ Cartela {cartela_id} já está livre.")
            return

        comprador = self.compradores.get(comprador_id)
        nome_comprador = comprador['nome'] if comprador else "Comprador Desconhecido"

        if messagebox.askyesno("Confirmar Desvinculação", 
                               f"Tem certeza que deseja desvincular a Cartela {cartela_id} de:\n👤 {nome_comprador} (ID: {comprador_id})?"):
            try:
                # 1. Desvincula a cartela:
                cartela['comprador_id'] = None
                log_message("INFO", f"Cartela {cartela_id} desvinculada de {comprador_id} ('{nome_comprador}').")

                # 2. Remove a cartela da lista do comprador (se o comprador existir)
                if comprador and cartela_id in comprador.get('cartelas', []):
                    comprador['cartelas'].remove(cartela_id)
                
                # 3. Se o comprador ficar sem cartelas, remove-o 
                if comprador and not comprador['cartelas']:
                    del self.compradores[comprador_id]
                    log_message("INFO", f"Comprador {comprador_id} ('{nome_comprador}') removido por não ter mais cartelas.")
                    messagebox.showinfo("Sucesso", f"✅ Comprador {nome_comprador} (ID: {comprador_id}) removido por não ter mais cartelas.")
                
                self.save_data()
                
                # 🐞 CORREÇÃO DO ERRO: Adia as chamadas para prevenir "invalid command name"
                self.root.after(100, self.atualizar_status)
                self.root.after(100, self.atualizar_lista_compradores)
                self.root.after(100, self.atualizar_info_cartelas)
                
                messagebox.showinfo("Sucesso", f"✅ Cartela {cartela_id} desvinculada e agora está LIVRE.")

            except Exception as e:
                log_message("ERROR", f"Falha ao desvincular cartela {cartela_id}: {e}")
                messagebox.showerror("Erro de Desvinculação", f"Falha ao desvincular cartela: {e}")

    # --- Métodos de Sorteio (MODIFICADOS) ---
    
    def sortear_numero(self):
        # ... (Mantido, com uso da variável de instância self.numero_maximo)
        if not self.cartelas_geradas:
            messagebox.showwarning("Atenção", "⚠️ Gere as cartelas primeiro!")
            return

        numeros_disponiveis = [n for n in range(1, self.numero_maximo + 1) if n not in self.numeros_sorteados] # [MODIFICADO]
        
        if not numeros_disponiveis:
            log_message("WARNING", "Tentativa de sorteio: todos os números já foram sorteados.")
            messagebox.showinfo("Fim do Jogo", "Todos os números já foram sorteados!")
            return
            
        numero_sorteado = random.choice(numeros_disponiveis)
        self._processar_sorteio(numero_sorteado)
        
    def inserir_numero_manual(self):
        # ... (Mantido, com uso da variável de instância self.numero_maximo)
        if not self.cartelas_geradas:
            messagebox.showwarning("Atenção", "⚠️ Gere as cartelas primeiro!")
            return

        try:
            numero_text = self.entry_numero_manual.get()
            if not numero_text:
                messagebox.showwarning("Atenção", "Insira um número para sortear.")
                return

            numero = int(numero_text)
            
            if not 1 <= numero <= self.numero_maximo: # [MODIFICADO]
                messagebox.showwarning("Atenção", f"O número deve estar entre 1 e {self.numero_maximo}.")
                return
            
            if numero in self.numeros_sorteados:
                messagebox.showwarning("Atenção", f"O número {numero} já foi sorteado!")
                return
                
            self._processar_sorteio(numero)
            self.entry_numero_manual.delete(0, 'end')
            
        except ValueError:
            messagebox.showwarning("Atenção", "Insira um número válido.")
            
    def _processar_sorteio(self, numero_sorteado):
        # ... (Mantido)
        self.numeros_sorteados.add(numero_sorteado)
        self.ultimo_numero_sorteado = numero_sorteado
        
        log_message("INFO", f"Número sorteado: {numero_sorteado}")
        
        vencedor_encontrado = False 
        
        for cartela_id, cartela in self.cartelas.items():
            if numero_sorteado in cartela['numeros']:
                cartela['acertos'] += 1
                if cartela['acertos'] == 25:
                    vencedor_encontrado = True
                    # Atualiza o vencedor assim que o BINGO for alcançado
                    self.cartela_vencedora = cartela_id
        
        self.historico_sorteios.append({
            'numero': numero_sorteado,
            'hora': datetime.now().strftime("%H:%M:%S")
        })
        
        self.save_data()
        self.atualizar_status()
        self.atualizar_display_numero()
        self.atualizar_historico()
        self.mostrar_top20_no_sorteio()
        
        if vencedor_encontrado:
            self._verificar_vencedor_automatico()

    def _verificar_vencedor_automatico(self):
        # ... (Mantido)
        vencedores = [cid for cid, cartela in self.cartelas.items() if cartela['acertos'] == 25]
        
        if vencedores:
            log_message("SUCCESS", f"BINGO! Vencedor(es) encontrado(s): {vencedores}")
            self.root.after(100, lambda: self.display_vencedor(vencedores[0], vencedores))

    def verificar_vencedor(self):
        # ... (Mantido)
        if not self.cartelas_geradas:
            messagebox.showwarning("Atenção", "⚠️ Gere as cartelas primeiro!")
            return
            
        vencedores = [cid for cid, cartela in self.cartelas.items() if cartela['acertos'] == 25]
        
        if vencedores:
            self.display_vencedor(vencedores[0], vencedores)
        else:
            messagebox.showinfo("Resultado", "Ainda não há vencedores com 25 acertos.")

    def display_vencedor(self, cartela_id, todos_vencedores):
        # ... (Mantido)
        vencedor_window = ctk.CTkToplevel(self.root)
        vencedor_window.title("🎉 VENCEDOR(A) ENCONTRADO(A) 🎉")
        vencedor_window.geometry("500x350")
        vencedor_window.transient(self.root)
        vencedor_window.grab_set()

        cartela_data = self.cartelas.get(cartela_id, {})
        comprador_id = cartela_data.get('comprador_id')
        
        if comprador_id and comprador_id in self.compradores:
            comprador = self.compradores[comprador_id]
            nome = comprador['nome']
            celular = comprador['celular']
            vendedor = comprador['vendedor']
        else:
            nome, celular, vendedor = "NÃO ATRIBUÍDA", "---", "---"

        ctk.CTkLabel(vencedor_window, text="🏆 BINGO! TEMOS UM VENCEDOR! 🏆", 
                      font=("Arial", 22, "bold"), text_color="#FFD700").pack(pady=15)
        
        ctk.CTkLabel(vencedor_window, text=f"CARTELA VENCEDORA (ID):", 
                      font=("Arial", 16)).pack(pady=5)
        ctk.CTkLabel(vencedor_window, text=f"{cartela_id}", 
                      font=("Arial", 36, "bold"), text_color="#4CAF50").pack(pady=5)
                      
        ctk.CTkLabel(vencedor_window, text=f"NOME DO COMPRADOR:", 
                      font=("Arial", 16)).pack(pady=5)
        ctk.CTkLabel(vencedor_window, text=f"{nome}", 
                      font=("Arial", 24, "bold"), text_color="#2196F3").pack(pady=5)

        ctk.CTkLabel(vencedor_window, text=f"Celular: {celular} | Vendedor: {vendedor}", 
                      font=("Arial", 14)).pack(pady=10)
        
        if len(todos_vencedores) > 1:
            ctk.CTkLabel(vencedor_window, text=f"⚠️ {len(todos_vencedores)} Cartelas Vencedoras Encontradas!", 
                          font=("Arial", 12), text_color="#F44336").pack(pady=5)
            
        ctk.CTkButton(vencedor_window, text="FECHAR", command=vencedor_window.destroy).pack(pady=15)

    def reiniciar_sorteio(self):
        # ... (Mantido)
        """Reinicia o sorteio atual, zerando acertos e números sorteados"""
        if not self.cartelas_geradas:
            messagebox.showwarning("Atenção", "⚠️ Gere as cartelas primeiro!")
            return

        if messagebox.askyesno("Confirmar Reinício", 
                               "⚠️ Deseja realmente reiniciar o sorteio?\nTodos os números sorteados e acertos serão zerados."):
            self.numeros_sorteados = set()
            self.historico_sorteios = []
            self.ultimo_numero_sorteado = None
            self.cartela_vencedora = None # Zera o vencedor
            
            for cartela in self.cartelas.values():
                cartela['acertos'] = 0
                
            self.save_data()
            self.atualizar_status()
            self.atualizar_display_numero()
            self.atualizar_historico()
            self.mostrar_top20_no_sorteio()
            log_message("WARNING", "Sorteio reiniciado (Números sorteados e acertos zerados).")
            messagebox.showinfo("Sucesso", "Sorteio reiniciado com sucesso!")

    def atualizar_display_numero(self):
        # ... (Mantido)
        if hasattr(self, 'numero_display'):
            if self.ultimo_numero_sorteado is not None:
                self.numero_display.configure(text=str(self.ultimo_numero_sorteado))
            else:
                self.numero_display.configure(text="--")
            
    def atualizar_historico(self):
        # ... (Mantido)
        if not hasattr(self, 'historico_container_frame') or not self.historico_container_frame.winfo_exists(): return
        
        for widget in self.historico_container_frame.winfo_children():
            widget.destroy()
        
        if not self.historico_sorteios:
            CTkLabel(self.historico_container_frame, text="Nenhum número sorteado ainda.", 
                     font=("Arial", 12)).pack(padx=10, pady=10)
            return
            
        sorted_numeros = sorted([h['numero'] for h in self.historico_sorteios])
        
        numbers_frame = CTkFrame(self.historico_container_frame, fg_color="transparent")
        numbers_frame.pack(side="left", fill="y", padx=5)
        
        for i, numero in enumerate(sorted_numeros):
            num_label = CTkLabel(numbers_frame, text=f"{numero:02d}", 
                                 font=("Arial", 14, "bold"), 
                                 text_color="#FFFFFF",
                                 fg_color="#333333", width=30, height=30, corner_radius=5)
            num_label.pack(side="left", padx=2, pady=5)


    # --- Métodos de Exportação (PDF - Mantidos) ---

    def exportar_pdf(self):
        # ... (Mantido)
        """Exporta as cartelas para PDF para Gráfica (Sem marcações e sem BINGO)"""
        if not self.cartelas:
            messagebox.showwarning("Atenção", "⚠️ Gere as cartelas primeiro!")
            return
        
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=f"cartelas_grafica_{self.concurso_atual}_{datetime.now().strftime('%Y%m%d')}.pdf"
            )
            
            if filename:
                loading = LoadingWindow(self.root, "Exportando PDF (Gráfica)...")
                log_message("INFO", f"Iniciando exportação de PDF para gráfica: {filename}")
                
                def exportar_em_thread():
                    try:
                        c = canvas.Canvas(filename, pagesize=A4)
                        width, height = A4
                        
                        cartelas_por_pagina = 6
                        cartelas_processadas = 0
                        total_cartelas = len(self.cartelas)
                        
                        cartela_ids_ordenadas = sorted(self.cartelas.keys(), key=lambda x: int(x))

                        for cartela_id in cartela_ids_ordenadas:
                            cartela_data = self.cartelas[cartela_id]
                            
                            if cartelas_processadas % cartelas_por_pagina == 0 and cartelas_processadas > 0:
                                c.showPage()
                            
                            row = (cartelas_processadas % cartelas_por_pagina) // 2
                            col = (cartelas_processadas % cartelas_por_pagina) % 2
                            
                            x_offset = 50 + col * (width / 2 - 30)
                            y_offset = height - 150 - row * 200
                            
                            self._desenhar_cartela_grafica(c, cartela_id, cartela_data, x_offset, y_offset)
                        
                            cartelas_processadas += 1
                            progress = cartelas_processadas / total_cartelas
                            self.root.after(0, lambda p=progress: 
                                            loading.update_progress(p, f"Exportando cartela {cartelas_processadas}/{total_cartelas}..."))
                        
                        c.save()
                        
                        self.root.after(0, 
                                        lambda: [
                                            loading.close(),
                                            log_message("SUCCESS", f"PDF para gráfica exportado com sucesso: {filename}"),
                                            messagebox.showinfo("Sucesso", f"✅ PDF para gráfica exportado com sucesso!\n📁 {filename}")
                                        ])
                        
                    except Exception as e:
                        log_message("ERROR", f"Erro fatal ao exportar PDF: {str(e)}")
                        self.root.after(0, lambda: [
                            loading.close(),
                            messagebox.showerror("Erro", f"❌ Erro ao exportar PDF: {str(e)}")
                        ])
                
                threading.Thread(target=exportar_em_thread, daemon=True).start()
                
        except Exception as e:
            log_message("ERROR", f"Erro no diálogo de exportação de PDF: {str(e)}")
            messagebox.showerror("Erro", f"❌ Erro ao exportar PDF: {str(e)}")

    def _desenhar_cartela_grafica(self, c, cartela_id, cartela_data, x, y):
        # ... (Mantido)
        """Desenha a cartela no PDF *sem BINGO e sem marcações*"""
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x, y, f"Cartela #{cartela_id.zfill(3)}")
        
        if cartela_data.get('comprador_id') and cartela_data['comprador_id'] in self.compradores:
            comprador = self.compradores[cartela_data['comprador_id']]
            c.setFont("Helvetica", 8)
            c.drawString(x, y - 15, f"Comprador: {comprador['nome']}")
        
        cell_size = 25
        
        for i in range(5):
            for j in range(5):
                cell_x = x + j * cell_size
                cell_y = y - 30 - i * cell_size - 10 
                
                c.rect(cell_x, cell_y, cell_size, cell_size)
                
                numero = cartela_data['numeros'][i * 5 + j]
                c.setFont("Helvetica", 10)
                c.setFillColorRGB(0, 0, 0) # Cor preta garantida
                c.drawCentredString(cell_x + cell_size/2, cell_y + cell_size/2 - 3, str(numero))

    # --- Métodos de Exportação (Excel - Mantidos) ---

    def exportar_excel(self):
        # ... (Mantido)
        if not self.cartelas:
            messagebox.showwarning("Atenção", "⚠️ Gere as cartelas primeiro!")
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"bingo_completo_{self.concurso_atual}_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
            
            if filename:
                loading = LoadingWindow(self.root, "Exportando Excel...")
                log_message("INFO", f"Iniciando exportação de Excel: {filename}")
                
                def exportar_em_thread():
                    try:
                        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                            
                            cartelas_data = []
                            cartela_ids_ordenadas = sorted(self.cartelas.keys(), key=lambda x: int(x))
                            
                            for cartela_id in cartela_ids_ordenadas:
                                cartela = self.cartelas[cartela_id]
                                comprador_nome = "Não atribuído"
                                vendedor_nome = "Não atribuído"
                                
                                if cartela.get('comprador_id') and cartela['comprador_id'] in self.compradores:
                                    comprador = self.compradores[cartela['comprador_id']]
                                    comprador_nome = comprador['nome']
                                    vendedor_nome = comprador['vendedor']
                                
                                row = [cartela_id.zfill(3), cartela['acertos'], comprador_nome, vendedor_nome] + cartela['numeros']
                                cartelas_data.append(row)
                                
                            colunas = ['Cartela ID', 'Acertos', 'Comprador', 'Vendedor'] + [f'N{i+1}' for i in range(25)]
                            df_cartelas = pd.DataFrame(cartelas_data, columns=colunas)
                            df_cartelas.to_excel(writer, sheet_name='Cartelas', index=False)
                            
                            if self.compradores:
                                compradores_data = []
                                comprador_ids_ordenados = sorted(self.compradores.keys(), key=lambda x: int(x))
                                
                                for comp_id in comprador_ids_ordenados:
                                    comprador = self.compradores[comp_id]
                                    cartelas_str = ', '.join(comprador.get('cartelas', []))
                                    compradores_data.append([
                                        comp_id.zfill(3), comprador['nome'], comprador['endereco'],
                                        comprador['celular'], comprador['vendedor'], 
                                        cartelas_str, comprador['data_cadastro']
                                    ])
                            
                                df_compradores = pd.DataFrame(compradores_data, 
                                                              columns=['ID', 'Nome', 'Endereço', 'Celular', 
                                                                       'Vendedor', 'Cartelas', 'Data Cadastro'])
                                df_compradores.to_excel(writer, sheet_name='Compradores', index=False)
                            
                            sorteio_data = [
                                ['Concurso', self.concurso_atual],
                                ['Total números sorteados', len(self.numeros_sorteados)],
                                ['Cartela vencedora', self.cartela_vencedora or 'Não definida'],
                                ['Data exportação', datetime.now().strftime("%d/%m/%Y %H:%M")]
                            ]
                            if self.numeros_sorteados:
                                sorteio_data.append(['Números sorteados', ', '.join(map(str, sorted(self.numeros_sorteados)))])
                            
                            df_sorteio = pd.DataFrame(sorteio_data, columns=['Item', 'Valor'])
                            df_sorteio.to_excel(writer, sheet_name='Sorteio', index=False)
                        
                        self.root.after(0, lambda: [
                            loading.close(),
                            log_message("SUCCESS", f"Excel exportado com sucesso: {filename}"),
                            messagebox.showinfo("Sucesso", f"✅ Excel exportado com sucesso!\n📁 {filename}")
                        ])
                    
                    except Exception as e:
                        log_message("ERROR", f"Erro fatal ao exportar Excel: {str(e)}")
                        self.root.after(0, lambda: [
                            loading.close(),
                            messagebox.showerror("Erro", f"❌ Erro ao exportar Excel: {str(e)}")
                        ])
                
                threading.Thread(target=exportar_em_thread, daemon=True).start()
                
        except Exception as e:
            log_message("ERROR", f"Erro no diálogo de exportação de Excel: {str(e)}")
            messagebox.showerror("Erro", f"❌ Erro ao exportar Excel: {str(e)}")

    # --- Métodos de Cartelas (Visualizar com Busca - Mantidos) ---

    def visualizar_cartela(self):
        # ... (Mantido)
        """Visualiza uma cartela específica (COM busca por ID/Enter e dropdown)"""
        if not self.cartelas:
            messagebox.showwarning("Atenção", "⚠️ Nenhuma cartela gerada!")
            return
        
        cartela_ids = sorted(self.cartelas.keys(), key=int)
        
        janela = ctk.CTkToplevel(self.root)
        janela.title("Visualizar Cartela")
        janela.geometry("400x550")
        janela.transient(self.root)
        janela.grab_set()
        
        search_frame = CTkFrame(janela)
        search_frame.pack(pady=10, padx=20)
        
        CTkLabel(search_frame, text="Buscar ID:", font=("Arial", 12)).pack(side="left", padx=5)
        
        entry_var = tk.StringVar(value=cartela_ids[0])
        entry_cartela = CTkEntry(search_frame, textvariable=entry_var, width=80)
        entry_cartela.pack(side="left", padx=5)

        CTkLabel(search_frame, text="ou Rolar:", font=("Arial", 12)).pack(side="left", padx=5)
        cartela_var_combo = ctk.StringVar(value=cartela_ids[0])
        cartela_combo = ctk.CTkComboBox(search_frame, values=cartela_ids, variable=cartela_var_combo, width=100)
        cartela_combo.pack(side="left", padx=5)
        
        cartela_frame = CTkFrame(janela)
        cartela_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        def mostrar_cartela(cartela_id):
            if cartela_id not in self.cartelas:
                for widget in cartela_frame.winfo_children(): widget.destroy()
                CTkLabel(cartela_frame, text=f"Cartela ID {cartela_id} inválida ou inexistente.", text_color="red").pack(pady=20)
                return
                
            for widget in cartela_frame.winfo_children(): widget.destroy()
            
            cartela = self.cartelas[cartela_id]
            
            CTkLabel(cartela_frame, text=f"Cartela #{cartela_id.zfill(3)}", 
                     font=("Arial", 16, "bold")).pack(pady=10)
            
            letras_frame = CTkFrame(cartela_frame)
            letras_frame.pack(pady=5)
            
            letras = ['B', 'I', 'N', 'G', 'O']
            for letra in letras:
                CTkLabel(letras_frame, text=letra, width=40, height=30,
                         font=("Arial", 14, "bold"), 
                         fg_color="#444444", text_color="white").pack(side="left", padx=2) 
            
            grade_frame = CTkFrame(cartela_frame)
            grade_frame.pack(pady=10)
            
            for i in range(5):
                row_frame = CTkFrame(grade_frame)
                row_frame.pack()
                for j in range(5):
                    numero = cartela['numeros'][i * 5 + j]
                    foi_sorteado = numero in self.numeros_sorteados
                    
                    cell_color = "#FF4444" if foi_sorteado else "#2B2B2B"
                    
                    cell = CTkFrame(row_frame, width=40, height=40, 
                                    fg_color=cell_color)
                    cell.pack(side="left", padx=2, pady=2)
                    cell.pack_propagate(False)
                    
                    CTkLabel(cell, text=str(numero), 
                             font=("Arial", 12, "bold"),
                             text_color="white").pack(expand=True)
            
            info_text = f"Acertos: {cartela['acertos']}/25\n"
            if cartela.get('comprador_id') and cartela['comprador_id'] in self.compradores:
                comprador = self.compradores[cartela['comprador_id']]
                info_text += f"Comprador: {comprador['nome']}\n"
                info_text += f"Celular: {comprador['celular']}\n"
                info_text += f"Vendedor: {comprador['vendedor']}"
            else:
                info_text += "Comprador: Não atribuído"
            
            CTkLabel(cartela_frame, text=info_text, font=("Arial", 12)).pack(pady=10)
            
            entry_var.set(cartela_id)
            cartela_var_combo.set(cartela_id)

        def on_entry_change(event=None):
            cartela_id = entry_var.get().strip()
            if cartela_id.isdigit() and cartela_id in self.cartelas:
                mostrar_cartela(cartela_id)
            elif event and event.keysym == 'Return':
                 messagebox.showwarning("Atenção", f"Cartela ID {cartela_id} inválida ou inexistente.")

        def on_combo_change(selected_id):
            entry_var.set(selected_id)
            mostrar_cartela(selected_id)

        entry_cartela.bind("<Return>", on_entry_change)
        cartela_combo.configure(command=on_combo_change)
        
        mostrar_cartela(cartela_ids[0])

    # --- Métodos de Concurso (Limpar Tudo - Mantidos) ---

    def limpar_tudo_definitivo(self):
        # ... (Mantido)
        """Reseta completamente o programa, excluindo todos os dados salvos e concursos."""
        log_message("WARNING", "Iniciando processo de RESET TOTAL.")
        if messagebox.askyesno("⚠️ RESETAR O SISTEMA", 
                               "⚠️ TEM CERTEZA ABSOLUTA?\n\n"
                               "Esta ação irá APAGAR:\n"
                               "• Todos os dados do concurso atual (Cartelas, Compradores, Sorteios)\n"
                               "• Todos os concursos salvos no diretório 'concursos'\n\n"
                               "O programa será reiniciado em um estado TOTALMENTE limpo. **Esta ação não pode ser desfeita.**"):
            
            try:
                # 1. Limpa os dados do programa (em memória)
                self.cartelas = {}
                self.compradores = {}
                self.numeros_sorteados = set()
                self.cartela_vencedora = None
                self.historico_sorteios = []
                self.ultimo_numero_sorteado = None
                self.concursos = {}
                self.concurso_atual = "Principal"
                self.cartelas_geradas = False
                self.cartelas_geradas_uma_vez = False # [MODIFICADO] Zera a flag de restrição
                
                # 2. Deleta os arquivos persistentes
                if os.path.exists('data/compradores.json'): os.remove('data/compradores.json')
                if os.path.exists('data/cartelas.json'): os.remove('data/cartelas.json')
                if os.path.exists('data/sorteio.json'): os.remove('data/sorteio.json')
                if os.path.exists('data/concursos.json'): os.remove('data/concursos.json')
                if os.path.exists('data/meta.json'): os.remove('data/meta.json') # [ADICIONADO]
                
                # 3. Deleta todos os arquivos de concursos salvos
                for filename in os.listdir('concursos'):
                    if filename.endswith('.json'):
                        os.remove(os.path.join('concursos', filename))
                        
                log_message("SUCCESS", "Sistema resetado. Reiniciando a aplicação.")
                messagebox.showinfo("Sucesso", "✅ Sistema resetado. Reiniciando o programa.")
                
                # 4. Reinicia a aplicação (fechando a janela e reabrindo)
                self.root.destroy()
                # Esta linha executa um novo processo do script principal.
                # Nota: Em executáveis PyInstaller, sys.executable aponta para o binário.
                os.execv(sys.executable, ['python'] + sys.argv)
                
            except Exception as e:
                log_message("FATAL", f"Falha ao resetar completamente: {e}")
                messagebox.showerror("Erro de Reset", f"Falha ao resetar completamente: {e}")

    # --- Métodos de Concurso (Mantidos) ---
    
    def atualizar_lista_concursos(self):
        # ... (Mantido)
        if not hasattr(self, 'concursos_list') or not self.concursos_list.winfo_exists(): return
        
        self.concursos_list.delete("1.0", "end")
        
        if self.concursos:
            for nome, meta in self.concursos.items():
                status_atual = " (ATUAL)" if nome == self.concurso_atual else ""
                self.concursos_list.insert("end", 
                    f"📋 {nome}{status_atual}\n"
                    f"    Cartelas: {meta.get('cartelas_count', 0)} | "
                    f"Compradores: {meta.get('compradores_count', 0)}\n"
                    f"    Último salvamento: {meta.get('data_salvamento', 'N/A')}\n"
                    f"{'─'*50}\n"
                )
        else:
            self.concursos_list.insert("end", "Nenhum concurso salvo.")

    def novo_concurso_dialog(self):
        # ... (Mantido, com reset da nova variável)
        if messagebox.askyesno("Novo Concurso", 
                               "Deseja salvar o concurso atual antes de criar um novo?"):
            if not self.salvar_concurso_atual():
                return
        
        nome_novo = simpledialog.askstring("Novo Concurso", "Digite o NOME do novo concurso (Ex: NATAL 2025):")
        if not nome_novo: return
        
        self.concurso_atual = nome_novo
        self.cartelas = {}
        self.compradores = {}
        self.numeros_sorteados = set()
        self.cartela_vencedora = None
        self.historico_sorteios = []
        self.ultimo_numero_sorteado = None
        self.cartelas_geradas = False 
        self.cartelas_geradas_uma_vez = False # [MODIFICADO] Zera a flag para permitir nova geração
        # Reseta as configurações para o default
        self.numero_maximo = DEFAULT_NUMERO_MAXIMO
        self.total_cartelas = DEFAULT_TOTAL_CARTELAS
        self.save_data()
        self.atualizar_status()
        self.atualizar_lista_concursos()
        self.update_ui_state() 
        log_message("INFO", f"Novo concurso '{nome_novo}' iniciado. Estado de UI resetado.")
        messagebox.showinfo("Sucesso", f"Concurso '{nome_novo}' iniciado. Gere as novas cartelas.")
    
    def salvar_concurso_atual(self):
        # ... (Mantido)
        nome_salvar = simpledialog.askstring("Salvar Concurso", "Nome do Concurso para salvar:", initialvalue=self.concurso_atual)
        if not nome_salvar: return False

        try:
            # Garantindo que a cartela vencedora salva é a que realmente venceu (ou None)
            vencedor_salvar = self.cartela_vencedora if self.cartela_vencedora in self.cartelas else None

            dados = {
                'cartelas': self.cartelas,
                'compradores': self.compradores,
                # Salva as configurações atuais de geração [ADICIONADO]
                'config_geracao': {
                    'numero_maximo': self.numero_maximo,
                    'total_cartelas': self.total_cartelas,
                    'cartelas_geradas_uma_vez': self.cartelas_geradas_uma_vez
                },
                'sorteio': {
                    'numeros_sorteados': list(self.numeros_sorteados),
                    'cartela_vencedora': vencedor_salvar, 
                    'historico_sorteios': self.historico_sorteios,
                    'ultimo_numero_sorteado': self.ultimo_numero_sorteado
                }
            }
            
            caminho_arquivo = f'concursos/{nome_salvar}.json'
            with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
                
            self.concursos[nome_salvar] = {
                'data_salvamento': datetime.now().strftime("%d/%m/%Y %H:%M"),
                'cartelas_count': len(self.cartelas),
                'compradores_count': len(self.compradores)
            }
            
            self.concurso_atual = nome_salvar
            self.save_data()
            self.atualizar_lista_concursos()
            self.atualizar_status()
            log_message("SUCCESS", f"Concurso '{nome_salvar}' salvo com sucesso.")
            messagebox.showinfo("Sucesso", f"Concurso '{nome_salvar}' salvo com sucesso!")
            return True
        except Exception as e:
            log_message("ERROR", f"Falha ao salvar concurso '{nome_salvar}': {e}")
            messagebox.showerror("Erro ao Salvar", f"Falha ao salvar concurso: {e}")
            return False

    def carregar_concurso_dialog(self):
        # ... (Mantido)
        if not self.concursos:
            messagebox.showwarning("Atenção", "Nenhum concurso salvo para carregar.")
            return

        concursos_list = list(self.concursos.keys())
        
        janela = ctk.CTkToplevel(self.root)
        janela.title("Carregar Concurso")
        janela.geometry("400x150")
        
        CTkLabel(janela, text="Selecione o concurso para carregar:", font=("Arial", 14)).pack(pady=10)
        
        concurso_var = ctk.StringVar(value=concursos_list[0])
        concurso_combo = ctk.CTkComboBox(janela, values=concursos_list, variable=concurso_var)
        concurso_combo.pack(pady=5)
        
        def carregar():
            nome = concurso_var.get()
            janela.destroy()
            self._carregar_concurso(nome)
        
        CTkButton(janela, text="📂 Carregar", command=carregar).pack(pady=10)

    def _carregar_concurso(self, nome):
        # ... (Mantido, com carregamento das novas variáveis)
        if nome == self.concurso_atual:
            messagebox.showinfo("Info", f"O concurso '{nome}' já é o concurso atual.")
            return

        if self.cartelas and not messagebox.askyesno("Confirmar", 
                                                     f"Deseja salvar o concurso atual '{self.concurso_atual}' antes de carregar '{nome}'?"):
            pass
        elif self.cartelas:
            self.salvar_concurso_atual()

        try:
            caminho_arquivo = f'concursos/{nome}.json'
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                dados = json.load(f)

            self.cartelas = dados.get('cartelas', {})
            self.compradores = dados.get('compradores', {})
            sorteio_data = dados.get('sorteio', {})
            config_data = dados.get('config_geracao', {}) # [ADICIONADO]
            
            self.numeros_sorteados = set(sorteio_data.get('numeros_sorteados', []))
            self.cartela_vencedora = sorteio_data.get('cartela_vencedora')
            self.historico_sorteios = sorteio_data.get('historico_sorteios', [])
            self.ultimo_numero_sorteado = sorteio_data.get('ultimo_numero_sorteado')
            
            # Carrega as configurações de geração, senão usa o default
            self.numero_maximo = config_data.get('numero_maximo', DEFAULT_NUMERO_MAXIMO) # [ADICIONADO]
            self.total_cartelas = config_data.get('total_cartelas', DEFAULT_TOTAL_CARTELAS) # [ADICIONADO]
            self.cartelas_geradas_uma_vez = config_data.get('cartelas_geradas_uma_vez', len(self.cartelas) > 0) # [ADICIONADO]

            self.concurso_atual = nome
            self.cartelas_geradas = len(self.cartelas) > 0 
            self.save_data()
            self.atualizar_status()
            
            self.root.after(0, lambda: [
                self.atualizar_info_cartelas(),
                self.atualizar_lista_compradores(),
                self.atualizar_display_numero(),
                self.atualizar_historico(),
                self.mostrar_top20_no_sorteio(),
                self.atualizar_lista_concursos(),
                self.update_ui_state(), 
                log_message("INFO", f"Concurso '{nome}' carregado com sucesso."),
                messagebox.showinfo("Sucesso", f"✅ Concurso '{nome}' carregado com sucesso!")
            ])

        except FileNotFoundError:
            log_message("ERROR", f"Arquivo do concurso '{nome}' não encontrado.")
            messagebox.showerror("Erro", f"Arquivo do concurso '{nome}' não encontrado.")
        except Exception as e:
            log_message("ERROR", f"Erro ao carregar concurso '{nome}': {e}")
            messagebox.showerror("Erro", f"Erro ao carregar concurso: {e}")

    def excluir_concurso_dialog(self):
        # ... (Mantido)
        if not self.concursos:
            messagebox.showwarning("Atenção", "Nenhum concurso salvo para excluir.")
            return

        concursos_list = [nome for nome in self.concursos.keys() if nome != self.concurso_atual]
        if not concursos_list:
             messagebox.showwarning("Atenção", "Não é possível excluir o único ou o concurso atual.")
             return

        janela = ctk.CTkToplevel(self.root)
        janela.title("Excluir Concurso")
        janela.geometry("400x150")
        
        CTkLabel(janela, text="Selecione o concurso para excluir:", font=("Arial", 14)).pack(pady=10)
        
        concurso_var = ctk.StringVar(value=concursos_list[0])
        concurso_combo = ctk.CTkComboBox(janela, values=concursos_list, variable=concurso_var)
        concurso_combo.pack(pady=5)
       
        def excluir():
            nome = concurso_var.get()
            if messagebox.askyesno("Confirmar Exclusão", 
                                   f"⚠️ Tem certeza que deseja excluir permanentemente o concurso '{nome}'?"):
                self._excluir_concurso(nome)
                janela.destroy()
        
        CTkButton(janela, text="🗑️ Excluir", command=excluir, fg_color="#F44336").pack(pady=10)

    def _excluir_concurso(self, nome):
        # ... (Mantido)
        try:
            if nome in self.concursos:
                caminho_arquivo = f'concursos/{nome}.json'
                if os.path.exists(caminho_arquivo):
                    os.remove(caminho_arquivo)
                
                del self.concursos[nome]
                self.save_data()
                self.atualizar_lista_concursos()
                log_message("WARNING", f"Concurso '{nome}' excluído permanentemente.")
                messagebox.showinfo("Sucesso", f"Concurso '{nome}' excluído com sucesso.")
            else:
                messagebox.showwarning("Atenção", f"Concurso '{nome}' não encontrado na lista.")
        except Exception as e:
            log_message("ERROR", f"Erro ao excluir concurso '{nome}': {e}")
            messagebox.showerror("Erro", f"Erro ao excluir concurso: {e}")

    # --- Métodos de Backup (Mantidos) ---

    def criar_backup(self):
        # ... (Mantido, com inclusão das novas variáveis)
        """Cria um arquivo de backup completo (.json) em um local escolhido pelo usuário."""
        try:
            # Consolida todos os dados em um único objeto JSON
            dados_backup = {
                'metadata': {
                    'concurso_atual': self.concurso_atual,
                    'versao_sistema': VERSAO_SISTEMA,
                    'data_backup': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'cartelas_geradas_uma_vez': self.cartelas_geradas_uma_vez,
                    'numero_maximo': self.numero_maximo, # [ADICIONADO]
                    'total_cartelas': self.total_cartelas # [ADICIONADO]
                },
                'cartelas': self.cartelas,
                'compradores': self.compradores,
                'sorteio': {
                    'numeros_sorteados': list(self.numeros_sorteados),
                    'cartela_vencedora': self.cartela_vencedora,
                    'historico_sorteios': self.historico_sorteios,
                    'ultimo_numero_sorteado': self.ultimo_numero_sorteado
                },
                'concursos_salvos': self.concursos # Também salva o metadado dos concursos salvos
            }

            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON Backup files", "*.json")],
                initialdir=os.path.join(os.getcwd(), 'backups'),
                initialfile=f"backup_bingo_{self.concurso_atual}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                title="Salvar Backup do Sistema"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(dados_backup, f, ensure_ascii=False, indent=4)
                
                log_message("SUCCESS", f"Backup criado com sucesso em: {filename}")
                messagebox.showinfo("Sucesso", f"✅ Backup criado com sucesso!\nSalve este arquivo em um local seguro.")

        except Exception as e:
            log_message("ERROR", f"Erro ao criar backup: {e}")
            messagebox.showerror("Erro de Backup", f"❌ Falha ao criar backup: {e}")

    def restaurar_backup(self):
        # ... (Mantido, com carregamento das novas variáveis)
        """Carrega dados de um arquivo de backup, sobrescrevendo o concurso atual."""
        if self.cartelas and not messagebox.askyesno("Confirmar Restauração", 
                                                     f"⚠️ A restauração irá **substituir todos os dados do concurso atual** ('{self.concurso_atual}')!\n"
                                                     "Deseja continuar com a restauração de um backup externo?"):
            return

        try:
            filename = filedialog.askopenfilename(
                defaultextension=".json",
                filetypes=[("JSON Backup files", "*.json")],
                initialdir=os.path.join(os.getcwd(), 'backups'),
                title="Abrir Arquivo de Backup"
            )

            if filename:
                with open(filename, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                
                # Extração e Carregamento de Dados
                self.cartelas = dados.get('cartelas', {})
                self.compradores = dados.get('compradores', {})
                self.concursos = dados.get('concursos_salvos', {})
                
                sorteio_data = dados.get('sorteio', {})
                self.numeros_sorteados = set(sorteio_data.get('numeros_sorteados', []))
                self.cartela_vencedora = sorteio_data.get('cartela_vencedora')
                self.historico_sorteios = sorteio_data.get('historico_sorteios', [])
                self.ultimo_numero_sorteado = sorteio_data.get('ultimo_numero_sorteado')

                # Extração de Metadados
                metadata = dados.get('metadata', {})
                self.concurso_atual = metadata.get('concurso_atual', 'Restaurado')
                self.cartelas_geradas = len(self.cartelas) > 0
                
                # Carrega as configurações de geração
                self.cartelas_geradas_uma_vez = metadata.get('cartelas_geradas_uma_vez', self.cartelas_geradas) # [ADICIONADO]
                self.numero_maximo = metadata.get('numero_maximo', DEFAULT_NUMERO_MAXIMO) # [ADICIONADO]
                self.total_cartelas = metadata.get('total_cartelas', DEFAULT_TOTAL_CARTELAS) # [ADICIONADO]

                # Salva o novo estado nos arquivos de dados
                self.save_data() 
                
                self.atualizar_status()
                self.root.after(0, lambda: [
                    self.atualizar_info_cartelas(),
                    self.atualizar_lista_compradores(),
                    self.atualizar_display_numero(),
                    self.atualizar_historico(),
                    self.mostrar_top20_no_sorteio(),
                    self.atualizar_lista_concursos(),
                    self.update_ui_state(), 
                    log_message("SUCCESS", f"Backup restaurado com sucesso. Concurso atual: {self.concurso_atual}"),
                    messagebox.showinfo("Sucesso", f"✅ Backup restaurado com sucesso!\nO concurso atual foi definido para: **{self.concurso_atual}**")
                ])

        except FileNotFoundError:
            messagebox.showwarning("Atenção", "Nenhum arquivo de backup selecionado ou arquivo não encontrado.")
        except json.JSONDecodeError:
            log_message("ERROR", "O arquivo de backup selecionado não é um JSON válido.")
            messagebox.showerror("Erro de Leitura", "❌ O arquivo de backup está corrompido ou não é um formato JSON válido.")
        except Exception as e:
            log_message("ERROR", f"Erro fatal ao restaurar backup: {e}")
            messagebox.showerror("Erro de Restauração", f"❌ Falha ao restaurar backup: {e}")


    # --- Métodos de Relatórios (Mantidos) ---
          
    def mostrar_top20_no_sorteio(self):
        # ... (Mantido)
        if not hasattr(self, 'top20_container_frame') or not self.top20_container_frame.winfo_exists(): return
        
        for widget in self.top20_container_frame.winfo_children():
            widget.destroy()

        if not self.cartelas:
            CTkLabel(self.top20_container_frame, text="⚠️ Nenhuma cartela gerada!", 
                     font=("Arial", 12)).pack(padx=10, pady=10)
            return
        
        cartelas_ordenadas = sorted(self.cartelas.items(), 
                                     key=lambda x: x[1]['acertos'], 
                                     reverse=True)[:20]
        
        for i, (cartela_id, cartela) in enumerate(cartelas_ordenadas, 1):
            comprador_nome = "Livre"
            
            if cartela['comprador_id'] and cartela['comprador_id'] in self.compradores:
                comprador = self.compradores[cartela['comprador_id']]
                comprador_nome = comprador['nome'][:10].strip()
            
            card_frame = CTkFrame(self.top20_container_frame, width=120, height=160)
            card_frame.pack(side="left", padx=5, pady=5, fill="y")
            card_frame.pack_propagate(False)

            CTkLabel(card_frame, text=f"#{i}", font=("Arial", 14, "bold"), text_color="#FFD700").pack(pady=(10, 5))
            CTkLabel(card_frame, text=f"ID: {cartela_id.zfill(3)}", font=("Arial", 12)).pack()
            CTkLabel(card_frame, text=f"{cartela['acertos']}/25", font=("Arial", 20, "bold"), text_color="#4CAF50").pack(pady=5)
            CTkLabel(card_frame, text=comprador_nome, font=("Arial", 10), text_color="#2196F3").pack()
            
            
    def mostrar_top20(self):
        # ... (Mantido)
        if not self.cartelas:
            messagebox.showwarning("Atenção", "⚠️ Nenhuma cartela gerada!")
            return
        
        self.relatorios_text.delete("1.0", "end")
        
        cartelas_ordenadas = sorted(self.cartelas.items(), 
                                     key=lambda x: x[1]['acertos'], 
                                     reverse=True)[:20]
        
        self.relatorios_text.insert("end", "🏆 TOP 20 CARTELAS COM MAIS ACERTOS\n\n")
        self.relatorios_text.insert("end", "Pos | Cartela ID | Acertos | Comprador (Vendedor)\n")
        self.relatorios_text.insert("end", "────┼────────────┼─────────┼──────────────────────\n")
        
        for i, (cartela_id, cartela) in enumerate(cartelas_ordenadas, 1):
            comprador_info = "Livre (---)"
            
            if cartela['comprador_id'] and cartela['comprador_id'] in self.compradores:
                comprador = self.compradores[cartela['comprador_id']]
                comprador_info = f"{comprador['nome']} (Vendedor: {comprador['vendedor']})"
            
            linha = f"{i:^3} | {cartela_id.zfill(3):^10} | {cartela['acertos']:^7d} | {comprador_info}\n"
            self.relatorios_text.insert("end", linha)

    def mostrar_vencedor(self):
        # ... (Mantido)
        vencedor_info = "Aguardando Sorteio"
        
        # Alterado para exibir o vencedor real (ou None)
        if self.cartela_vencedora:
            cartela = self.cartelas.get(self.cartela_vencedora)
            
            if not cartela:
                self.relatorios_text.delete("1.0", "end")
                self.relatorios_text.insert("end", "❌ Cartela vencedora registrada não encontrada! (Dados inconsistentes)")
                return
            
            vencedor_info = self.cartela_vencedora

            self.relatorios_text.delete("1.0", "end")
            self.relatorios_text.insert("end", f"🎯 CARTELA VENCEDORA: {self.cartela_vencedora}\n")
            self.relatorios_text.insert("end", f"📊 Acertos: {cartela['acertos']}/25\n\n")
            
            if cartela['comprador_id'] and cartela['comprador_id'] in self.compradores:
                comprador = self.compradores[cartela['comprador_id']]
                self.relatorios_text.insert("end", "👤 DADOS DO COMPRADOR VENCEDOR:\n")
                self.relatorios_text.insert("end", f"Nome: {comprador['nome']}\n")
                self.relatorios_text.insert("end", f"Endereço: {comprador['endereco']}\n")
                self.relatorios_text.insert("end", f"Celular: {comprador['celular']}\n")
                self.relatorios_text.insert("end", f"Vendedor: {comprador['vendedor']}\n")
                self.relatorios_text.insert("end", f"Cartelas: {', '.join(comprador.get('cartelas', []))}\n")
            else:
                self.relatorios_text.insert("end", "⚠️ Cartela não atribuída a comprador\n")
        else:
            self.relatorios_text.delete("1.0", "end")
            self.relatorios_text.insert("end", "⚠️ Cartela vencedora ainda não definida. Continue o sorteio ou verifique o vencedor.")
            
    def mostrar_estatisticas(self):
        # ... (Mantido, com uso da variável de instância self.numero_maximo)
        self.relatorios_text.delete("1.0", "end")
        
        self.relatorios_text.insert("end", "📈 ESTATÍSTICAS COMPLETAS DO BINGO\n\n")
        
        if not self.cartelas:
            self.relatorios_text.insert("end", "⚠️ Nenhuma cartela gerada para calcular estatísticas.")
            return

        cartelas_vendidas = sum(1 for c in self.cartelas.values() if c.get('comprador_id'))
        taxa_venda = (cartelas_vendidas/len(self.cartelas)*100) if self.cartelas else 0
        
        vencedor_info = self.cartela_vencedora if self.cartela_vencedora else "Não definida"

        self.relatorios_text.insert("end", f"📊 Total de Cartelas: {len(self.cartelas)}\n")
        self.relatorios_text.insert("end", f"🛒 Cartelas Vendidas: {cartelas_vendidas}\n")
        self.relatorios_text.insert("end", f"🆓 Cartelas Livres: {len(self.cartelas) - cartelas_vendidas}\n")
        self.relatorios_text.insert("end", f"📈 Taxa de Venda: {taxa_venda:.1f}%\n")
        self.relatorios_text.insert("end", f"👥 Compradores Cadastrados: {len(self.compradores)}\n")
        self.relatorios_text.insert("end", f"🎯 Cartela Vencedora: {vencedor_info}\n")
        self.relatorios_text.insert("end", f"📋 Concurso: {self.concurso_atual}\n\n")
        
        self.relatorios_text.insert("end", "🎯 ESTATÍSTICAS DE ACERTOS:\n")
        acertos = [c['acertos'] for c in self.cartelas.values()]
        max_acertos = max(acertos) if acertos else 0
        min_acertos = min(acertos) if acertos else 0
        media_acertos = sum(acertos) / len(acertos) if acertos else 0
        
        self.relatorios_text.insert("end", f"Máximo de acertos: {max_acertos}/25\n")
        self.relatorios_text.insert("end", f"Mínimo de acertos: {min_acertos}/25\n")
        self.relatorios_text.insert("end", f"Média de acertos: {media_acertos:.1f}/25\n\n")
        
        quase_vencedoras = sorted(self.cartelas.items(), 
                                 key=lambda x: x[1]['acertos'], 
                                 reverse=True)
        
        self.relatorios_text.insert("end", "🔥 CARTELAS PRÓXIMAS A VENCER (Acertos >= 20):\n")
        proximas_encontradas = False
        for cartela_id, cartela in quase_vencedoras:
            if cartela['acertos'] >= 20:
                comprador_info = "Não atribuída"
                if cartela['comprador_id'] and cartela['comprador_id'] in self.compradores:
                    comprador = self.compradores[cartela['comprador_id']]
                    comprador_info = f"{comprador['nome']} (Vendedor: {comprador['vendedor']})"
                
                self.relatorios_text.insert("end", 
                    f"Cartela {cartela_id.zfill(3)}: {cartela['acertos']}/25 acertos | {comprador_info}\n")
                proximas_encontradas = True
        
        if not proximas_encontradas:
            self.relatorios_text.insert("end", "Nenhuma cartela com 20 ou mais acertos ainda.\n")
    
        self.relatorios_text.insert("end", "\n🎲 NÚMEROS SORTEADOS:\n")
        if self.numeros_sorteados:
            numeros_str = ', '.join(map(str, sorted(self.numeros_sorteados)))
            self.relatorios_text.insert("end", f"Total: {len(self.numeros_sorteados)}/{self.numero_maximo}\n") # [MODIFICADO]
            self.relatorios_text.insert("end", numeros_str + "\n")
        else:
            self.relatorios_text.insert("end", "Nenhum número sorteado.\n")
            
    def listar_compradores(self):
        # ... (Mantido)
        self.relatorios_text.delete("1.0", "end")
        self.relatorios_text.insert("end", "👥 LISTA COMPLETA DE COMPRADORES\n\n")
        
        if not self.compradores:
            self.relatorios_text.insert("end", "Nenhum comprador cadastrado.")
            return

        comprador_ids = sorted(self.compradores.keys(), key=lambda x: int(x))
        for cid in comprador_ids:
            comprador = self.compradores[cid]
            self.relatorios_text.insert("end", f"ID: {cid} | Nome: {comprador['nome']}\n")
            self.relatorios_text.insert("end", f"  Celular: {comprador['celular']} | Vendedor: {comprador['vendedor']}\n")
            self.relatorios_text.insert("end", f"  Endereço: {comprador['endereco']}\n")
            self.relatorios_text.insert("end", f"  Cartelas ({len(comprador['cartelas'])}): {', '.join(comprador['cartelas'])}\n")
            self.relatorios_text.insert("end", "---------------------------------------\n")
            
    def mostrar_cartelas_comprador(self):
        # ... (Mantido)
        comprador_id = simpledialog.askstring("Buscar Comprador", "Digite o ID do Comprador:")
        if not comprador_id: return
        
        comprador = self.compradores.get(comprador_id)
        if not comprador:
            messagebox.showerror("Erro", f"Comprador ID {comprador_id} não encontrado.")
            return
            
        self.relatorios_text.delete("1.0", "end")
        self.relatorios_text.insert("end", f"📋 CARTELAS DO COMPRADOR: {comprador['nome']} (ID: {comprador_id})\n\n")
        
        cartela_ids = sorted(comprador['cartelas'], key=int)
        for cartela_id in cartela_ids:
            cartela = self.cartelas.get(cartela_id)
            if cartela:
                numeros_str = ', '.join(map(str, cartela['numeros']))
                self.relatorios_text.insert("end", 
                                   f"Cartela {cartela_id.zfill(3)} (Acertos: {cartela['acertos']}):\n"
                                   f"  {numeros_str}\n")
            else:
                self.relatorios_text.insert("end", f"Cartela {cartela_id} (DADOS PERDIDOS)\n")

    # --- Execução Principal (Mantida) ---
    def run(self):
        try:
            self.root.mainloop()
        except Exception as e:
            log_message("FATAL", f"Erro fatal na mainloop: {str(e)}")
            messagebox.showerror("Erro", f"Erro fatal: {str(e)}")
        finally:
            self.save_data()
            log_message("INFO", "Aplicação encerrada.")

# --- Bloco de Inicialização (Mantido) ---
if __name__ == "__main__":
    try:
        app = BingoSystem()
        app.run()
    except Exception as e:
        log_message("FATAL", f"Falha ao iniciar o sistema: {str(e)}")
        messagebox.showerror("Erro", f"Falha ao iniciar o sistema: {str(e)}")

