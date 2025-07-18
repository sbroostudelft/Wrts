import glob
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import random


##############################################################################
# Helper Functions
##############################################################################

def calculate_mismatch(word1, word2):
    """
    Simple mismatch calculation:
    The mismatch is the sum of:
    - The difference in length
    - The count of different characters at each position (up to the length of the shorter word)
    This is a simplified approach (not a full Levenshtein distance).
    """
    word1 = word1.lower()
    word2 = word2.lower()
    len_diff = abs(len(word1) - len(word2))
    common_length = min(len(word1), len(word2))
    char_mismatch = sum(1 for i in range(common_length) if word1[i] != word2[i])
    return len_diff + char_mismatch


def parse_filename(filepath):
    """
    Parse a filename to extract:
    - The numeric prefix (level) if it exists, e.g. "02_vocab.xlsx" => level=2, base_name="vocab", ext=".xlsx"
    - If no numeric prefix is found, level=0, base_name is the entire filename (minus extension).
    Return (base_name, extension, level).
    """
    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)
    match = re.match(r'^(\d{2})_(.*)$', name)
    if match:
        level_str, base = match.groups()
        level = int(level_str)
        return base, ext, level
    else:
        return name, ext, 0


class LanguageLearnerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Language Learner")
        self.geometry("900x600")



        # Optionally configure a style for ttk widgets
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", font=("Helvetica", 12), padding=6)
        style.configure("TLabel", font=("Helvetica", 12))
        style.configure("TFrame", background="#F5F5F5")

        # DataFrame to store loaded words
        self.df = None

        # Cards and scheduling
        self.cards = []  # List of dictionaries with {source, target, ...}
        self.queue = []  # Main session queue
        self.final_queue = []  # Words to be repeated at session end
        self.current_card = None
        self.total_unique = 0
        self.correct_count = 0

        # For file naming with levels
        self.base_name = None  # The "base" name (e.g. "vocab")
        self.file_ext = None  # The original file extension (e.g. ".xlsx")
        self.level = 0  # The numeric prefix we parse from the loaded file

        # User settings
        self.source_lang_var = tk.StringVar()
        self.target_lang_var = tk.StringVar()
        self.learning_method_var = tk.StringVar(value="in_gedachten")  # or "dictee"
        self.mismatch_var = tk.IntVar(value=0)  # Allowed mismatch for dictee

        # Main frames
        self.file_selection_frame = None
        self.settings_frame = None
        self.session_frame = None
        self.end_frame = None
        self.fuse_frame = None

        self.setup_file_selection_frame()



    ##########################################################################
    # HOME / FILE SELECTION FRAME
    ##########################################################################

    def setup_file_selection_frame(self):
        """
        The first frame: user loads a file and chooses source & target languages,
        or navigates to 'Fuse Lists'.
        """
        if self.file_selection_frame:
            self.file_selection_frame.destroy()

        self.file_selection_frame = ttk.Frame(self, padding=20)
        self.file_selection_frame.pack(fill="both", expand=True)

        title_label = ttk.Label(self.file_selection_frame, text="Load a Word List", font=("Helvetica", 18, "bold"))
        title_label.pack(pady=10)

        load_btn = ttk.Button(self.file_selection_frame, text="Load File", command=self.load_file)
        load_btn.pack(pady=10)

        self.info_label = ttk.Label(self.file_selection_frame, text="No file loaded", foreground="blue")
        self.info_label.pack(pady=5)

        # Dropdowns for language selection
        ttk.Label(self.file_selection_frame, text="Source Language:").pack(pady=(20, 5))
        self.source_lang_menu = ttk.Combobox(self.file_selection_frame, textvariable=self.source_lang_var,
                                             state="readonly", width=30)
        self.source_lang_menu.pack()

        ttk.Label(self.file_selection_frame, text="Target Language:").pack(pady=(20, 5))
        self.target_lang_menu = ttk.Combobox(self.file_selection_frame, textvariable=self.target_lang_var,
                                             state="readonly", width=30)
        self.target_lang_menu.pack()

        self.next_button = ttk.Button(self.file_selection_frame, text="Next", command=self.go_to_settings)
        self.next_button.pack(pady=10)
        self.next_button.config(state="disabled")  # Enabled once file is loaded

        # Fuse Lists button
        fuse_button = ttk.Button(self.file_selection_frame, text="Fuse Lists", command=self.go_to_fuse_screen)
        fuse_button.pack(pady=10)

    def load_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("All Supported", "*.txt;*.dat;*.xlsx"),
                ("Text files", "*.txt"),
                ("Data files", "*.dat"),
                ("Excel files", "*.xlsx")
            ]
        )
        if not file_path:
            return

        # Parse the file name to get base_name, extension, and level
        base, ext, lvl = parse_filename(file_path)
        self.base_name = base
        self.file_ext = ext
        self.level = lvl

        try:
            if ext == ".xlsx":
                self.df = pd.read_excel(file_path)
            elif ext in [".txt", ".dat"]:
                # Try comma-separated; if that fails, try tab-separated
                try:
                    self.df = pd.read_csv(file_path, sep=",")
                except:
                    self.df = pd.read_csv(file_path, sep="\t")
            else:
                messagebox.showerror("Error", "Unsupported file type")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")
            return

        if self.df.empty:
            messagebox.showerror("Error", "Loaded file is empty")
            return

        # If columns are unnamed, rename them
        if all(str(col).startswith("Unnamed") for col in self.df.columns):
            self.df.columns = [f"Language {i + 1}" for i in range(len(self.df.columns))]

        # Populate language selection
        language_options = list(self.df.columns)
        self.source_lang_menu['values'] = language_options
        self.target_lang_menu['values'] = language_options
        if len(language_options) > 0:
            self.source_lang_menu.current(0)
        if len(language_options) > 1:
            self.target_lang_menu.current(1)

        self.info_label.config(text=f"Loaded file: {os.path.basename(file_path)}")
        self.next_button.config(state="normal")

    def go_to_settings(self):
        if self.source_lang_var.get() == self.target_lang_var.get():
            messagebox.showerror("Error", "Source and target languages must be different")
            return

        if self.df is None or self.df.empty:
            messagebox.showerror("Error", "No valid file loaded")
            return

        self.file_selection_frame.destroy()
        self.setup_settings_frame()

    ##########################################################################
    # FUSE SCREEN
    ##########################################################################
    def go_to_fuse_screen(self):
        """
        Switch to the fuse frame, where we list all available files in a folder
        and allow multi-selection for fusion.

        Optionally, we let the user pick a folder. If you'd prefer always using
        the current working directory, just remove the folder selection code
        and set folder_path = os.getcwd().
        """
        if self.file_selection_frame:
            self.file_selection_frame.destroy()

        # Optional: ask user to pick a folder
        folder_path = filedialog.askdirectory(title="Select Folder Containing Lists")
        if not folder_path:
            # If user cancels picking a folder, go back to home
            self.setup_file_selection_frame()
            return

        self.fuse_frame = ttk.Frame(self, padding=20)
        self.fuse_frame.pack(fill="both", expand=True)

        title_label = ttk.Label(self.fuse_frame, text="Fuse Lists", font=("Helvetica", 18, "bold"))
        title_label.pack(pady=10)

        info_label = ttk.Label(self.fuse_frame, text="Select two or more lists to fuse:")
        info_label.pack(pady=5)

        # Gather all supported files in the chosen folder
        pattern = os.path.join(folder_path, "*.*")
        all_files = glob.glob(pattern)
        valid_extensions = [".xlsx", ".txt", ".dat"]
        self.fuse_file_list = [f for f in all_files if os.path.splitext(f)[1].lower() in valid_extensions]

        # If no valid files, show a message and go back
        if not self.fuse_file_list:
            messagebox.showinfo("No Files Found",
                                f"No valid (.xlsx, .txt, .dat) files found in:\n{folder_path}")
            self.return_to_home_from_fuse()
            return

        # Listbox to display the files
        self.fuse_listbox = tk.Listbox(self.fuse_frame, selectmode=tk.MULTIPLE, width=80, height=15)
        self.fuse_listbox.pack(pady=10, fill="x", expand=False)

        # Insert file names
        for f in self.fuse_file_list:
            self.fuse_listbox.insert(tk.END, os.path.basename(f))

        # Buttons: Fuse / Back
        btn_frame = ttk.Frame(self.fuse_frame)
        btn_frame.pack(pady=10)

        fuse_btn = ttk.Button(btn_frame, text="Fuse", command=self.fuse_selected_files)
        fuse_btn.pack(side="left", padx=10)

        back_btn = ttk.Button(btn_frame, text="Back to Home", command=self.return_to_home_from_fuse)
        back_btn.pack(side="left", padx=10)

    def fuse_selected_files(self):
        """
        Read the selected files, parse them, check for consistent # of columns,
        prompt user if there's a mismatch, then produce a fused file with a new name.
        """
        selected_indices = self.fuse_listbox.curselection()
        if len(selected_indices) < 2:
            messagebox.showerror("Error", "Please select at least two files to fuse.")
            return

        # Gather the selected file paths
        selected_paths = [self.fuse_file_list[i] for i in selected_indices]

        dataframes = []
        base_names = []
        levels = []
        col_counts = []

        for path in selected_paths:
            base, ext, lvl = parse_filename(path)
            base_names.append(base)
            levels.append(lvl)

            # Load file
            try:
                if ext == ".xlsx":
                    df = pd.read_excel(path)
                elif ext in [".txt", ".dat"]:
                    try:
                        df = pd.read_csv(path, sep=",")
                    except:
                        df = pd.read_csv(path, sep="\t")
                else:
                    messagebox.showerror("Error", f"Unsupported file type: {ext}")
                    return
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load {path}: {e}")
                return

            # If columns are unnamed, rename them
            if df.columns.str.startswith("Unnamed").all():
                df.columns = [f"Language {i + 1}" for i in range(len(df.columns))]

            dataframes.append(df)
            col_counts.append(df.shape[1])

        # Check if all col_counts are the same
        all_same_columns = (len(set(col_counts)) == 1)
        if not all_same_columns:
            # Prompt user: continue with incomplete fusion or cancel
            ans = messagebox.askyesno(
                "Mismatch in # of Languages",
                "The selected lists do not have the same number of columns.\n"
                "Do you want to continue anyway (Fused Incomplete)?"
            )
            if not ans:
                return  # Cancel
            fused_type = "FI"  # Fused Incomplete
        else:
            fused_type = "FC"  # Fused Complete

        # Combine dataframes (outer concat so we don't lose any columns)
        fused_df = pd.concat(dataframes, axis=0, ignore_index=True, sort=False)

        # Keep the columns in the order they appear
        original_cols = list(fused_df.columns)
        fused_df = fused_df[original_cols]

        # Rename each to Language i
        new_col_names = {old: f"Language {i + 1}" for i, old in enumerate(original_cols)}
        fused_df.rename(columns=new_col_names, inplace=True)

        # Build the new file name
        max_level = max(levels)
        word_count = fused_df.shape[0]

        # Concatenate base names. If too long, keep only last two.
        combined_base = "+".join(base_names)
        if len(combined_base) > 40:  # arbitrary limit
            if len(base_names) > 2:
                combined_base = "+".join(base_names[-2:])

        lists_folder = os.path.join(os.getcwd(), "lists")
        os.makedirs(lists_folder, exist_ok=True)  # Ensure the folder exists

        # Now build the absolute path for the new file:
        new_filename = f"{max_level:02d}_{fused_type}_{combined_base}_{word_count}.xlsx"
        fused_file_path = os.path.join(lists_folder, new_filename)

        # Save
        try:
            fused_df.to_excel(fused_file_path, index=False)
            messagebox.showinfo("Success", f"Fused file created:\n{fused_file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not create fused file: {e}")

    def return_to_home_from_fuse(self):
        """
        Destroy fuse frame and go back to home screen.
        """
        if self.fuse_frame:
            self.fuse_frame.destroy()
        self.setup_file_selection_frame()

    ##########################################################################
    # SETTINGS FRAME
    ##########################################################################

    def setup_settings_frame(self):
        """
        A page to display the loaded words in a table, choose method (In Gedachten or Dictee),
        and if Dictee is chosen, set the mismatch threshold.
        """
        self.settings_frame = ttk.Frame(self, padding=20)
        self.settings_frame.pack(fill="both", expand=True)

        title_label = ttk.Label(self.settings_frame, text="Settings", font=("Helvetica", 18, "bold"))
        title_label.pack(pady=10)

        # Frame to hold the table of words
        table_frame = ttk.Frame(self.settings_frame)
        table_frame.pack(fill="both", expand=True, pady=10)

        # Show only the chosen source and target columns
        source_col = self.source_lang_var.get()
        target_col = self.target_lang_var.get()

        displayed_df = self.df[[source_col, target_col]].copy()
        displayed_df.columns = ["Source", "Target"]  # rename for clarity in the table

        # Create a Treeview to display the words
        self.word_table = ttk.Treeview(table_frame, columns=("source", "target"), show="headings", height=10)
        self.word_table.heading("source", text="Source")
        self.word_table.heading("target", text="Target")
        self.word_table.column("source", width=200)
        self.word_table.column("target", width=200)
        self.word_table.pack(side="left", fill="both", expand=True)

        # Add a scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.word_table.yview)
        scrollbar.pack(side="right", fill="y")
        self.word_table.configure(yscrollcommand=scrollbar.set)

        # Insert the words into the table
        for idx, row in displayed_df.iterrows():
            self.word_table.insert("", "end", values=(row["Source"], row["Target"]))

        # Frame for method selection
        method_frame = ttk.Frame(self.settings_frame)
        method_frame.pack(pady=10, fill="x")

        ttk.Label(method_frame, text="Learning Method:").pack(anchor="w", pady=5)
        # Radio buttons for method
        method_in_gedachten_rb = ttk.Radiobutton(
            method_frame, text="In Gedachten", variable=self.learning_method_var, value="in_gedachten",
            command=self.update_mismatch_state
        )
        method_in_gedachten_rb.pack(anchor="w")
        method_dictee_rb = ttk.Radiobutton(
            method_frame, text="Dictee", variable=self.learning_method_var, value="dictee",
            command=self.update_mismatch_state
        )
        method_dictee_rb.pack(anchor="w")

        # Spinbox for mismatch threshold (only relevant for dictee)
        mismatch_label = ttk.Label(method_frame, text="Allowed Letter Mismatch:")
        mismatch_label.pack(anchor="w", pady=(10, 0))
        self.mismatch_spinbox = ttk.Spinbox(method_frame, from_=0, to=10, textvariable=self.mismatch_var, width=5,
                                            state="disabled")
        self.mismatch_spinbox.pack(anchor="w")

        # Start session button
        start_session_btn = ttk.Button(self.settings_frame, text="Start Session", command=self.start_session)
        start_session_btn.pack(pady=20)

    def update_mismatch_state(self):
        """
        Enable/disable the mismatch spinbox depending on whether the user chose Dictee.
        """
        if self.learning_method_var.get() == "dictee":
            self.mismatch_spinbox.config(state="normal")
        else:
            self.mismatch_spinbox.config(state="disabled")

    def start_session(self):
        """
        Prepare the cards and go to the session frame.
        """
        source_lang = self.source_lang_var.get()
        target_lang = self.target_lang_var.get()
        if source_lang == target_lang:
            messagebox.showerror("Error", "Source and target languages must be different")
            return

        # Build cards
        self.cards = []
        for _, row in self.df.iterrows():
            source_word = str(row[source_lang])
            target_word = str(row[target_lang])
            card = {
                "source": source_word,
                "target": target_word,
                "delayed_scheduled": False,
                "final_scheduled": False,
                "completed": False,
                "incorrect_count": 0  # Track how many times user answered incorrectly
            }
            self.cards.append(card)

        self.total_unique = len(self.cards)
        self.correct_count = 0
        self.incorrect_overall = 0  # Keep track of total times answered incorrectly (for the session UI if desired)

        # Shuffle initial order
        random.shuffle(self.cards)
        self.queue = self.cards.copy()
        self.final_queue = []

        # Destroy the settings frame and show the session
        self.settings_frame.destroy()
        self.setup_session_frame()
        self.next_card()

    def setup_session_frame(self):
        """
        Display a WRTS-like layout:
          - Top header bar
          - Main content area with the question/answer
          - Running score
          - Shifted to the right by adding horizontal padding
        """
        # Create a main frame (session_frame) for everything
        # Add a left padding to shift the layout to the right (adjust as desired)
        self.session_frame = tk.Frame(self, bg="#F3F3F3")
        self.session_frame.pack(fill="both", expand=True, padx=100, pady=75)  # <--- SHIFT RIGHT

        ############################################################################
        # Top Header Bar
        ############################################################################
        header_frame = tk.Frame(self.session_frame, bg="#D5D0E5", height=50)
        header_frame.pack(fill="x", side="top")

        # "Wrts" label on the left
        wrts_label = tk.Label(
            header_frame, text="Wrts", font=("Helvetica", 18, "bold"),
            bg="#D5D0E5", fg="black"
        )
        wrts_label.pack(side="left", padx=20, pady=10)

        # A placeholder subtitle (customize or remove)
        subtitle_label = tk.Label(
            header_frame, text=f"Frans apprandre 2 h2 ({len(self.df) if self.df is not None else 0})", font=("Helvetica", 14),
            bg="#D5D0E5", fg="black"
        )
        subtitle_label.pack(side="left", padx=20)

        ############################################################################
        # Main Content
        ############################################################################
        content_frame = tk.Frame(self.session_frame, bg="#FDFBF6", bd=2, relief="groove")
        content_frame.pack(fill="both", expand=True, padx=30, pady=20)

        # The "Question" label: shows the source word
        self.question_label = tk.Label(
            content_frame, text="", font=("Helvetica", 16, "bold"),
            bg="#FDFBF6", fg="black"
        )
        self.question_label.pack(pady=(20, 5), anchor="w")

        # Feedback labels:
        # 1) feedback_label: "Het antwoord is fout" or "Het antwoord is goed"
        # 2) correct_answer_label: "Het goede antwoord is: XXX"
        self.feedback_label = tk.Label(content_frame, text="", font=("Helvetica", 14, "bold"),
                                       bg="#FDFBF6", fg="red")
        self.feedback_label.pack(pady=(5, 5), anchor="w")

        self.correct_answer_label = tk.Label(content_frame, text="", font=("Helvetica", 14),
                                             bg="#FDFBF6", fg="black")
        self.correct_answer_label.pack(pady=(0, 10), anchor="w")

        # Depending on the method, show different UI:
        if self.learning_method_var.get() == "dictee":
            # The user will type the answer in an Entry widget
            self.answer_entry = tk.Entry(content_frame, font=("Helvetica", 14), width=40)
            self.answer_entry.pack(pady=(5, 5), anchor="w")

            # A button to check the answer
            self.check_button = tk.Button(
                content_frame, text="OK", font=("Helvetica", 12, "bold"),
                command=self.check_dictee_answer, bg="#EEE", fg="black"
            )
            self.check_button.pack(pady=(5, 15), anchor="w")

        else:
            # "In Gedachten" method
            # Show a label for hidden/visible target
            self.answer_label = tk.Label(content_frame, text="???", font=("Helvetica", 16),
                                         bg="#FDFBF6", fg="gray")
            self.answer_label.pack(pady=(5, 10), anchor="w")

            # Show Answer button
            show_answer_btn = tk.Button(
                content_frame, text="Toon Antwoord", font=("Helvetica", 12, "bold"),
                command=self.show_answer, bg="#EEE", fg="black"
            )
            show_answer_btn.pack(pady=5, anchor="w")

            # Correct/Incorrect buttons
            button_frame = tk.Frame(content_frame, bg="#FDFBF6")
            button_frame.pack(pady=10, anchor="w")

            correct_btn = tk.Button(
                button_frame, text="Goed", font=("Helvetica", 12, "bold"),
                command=self.mark_correct, bg="#AEE8AE"
            )
            correct_btn.pack(side="left", padx=5)

            incorrect_btn = tk.Button(
                button_frame, text="Fout", font=("Helvetica", 12, "bold"),
                command=self.mark_incorrect, bg="#F8B4B4"
            )
            incorrect_btn.pack(side="left", padx=5)

        # Score label at the bottom
        self.score_label = tk.Label(
            content_frame, text="Score tot nu toe: 0 goed, 0 fout",
            font=("Helvetica", 12, "italic"), bg="#FDFBF6", fg="black"
        )
        self.score_label.pack(pady=(10, 20), anchor="w")

    def show_answer(self):
        """
        For "In Gedachten" method: reveal the target word.
        """
        if self.current_card:
            self.answer_label.config(text=self.current_card["target"])

    def mark_correct(self):
        """
        Mark the current card as answered correctly (In Gedachten).
        """
        if self.current_card and not self.current_card["completed"]:
            self.current_card["completed"] = True
            self.correct_count += 1
        self.update_score_label()
        self.next_card()

    def mark_incorrect(self):
        """
        Mark the current card as answered incorrectly (In Gedachten).
        Schedule it for repetition.
        """
        if self.current_card:
            self.current_card["incorrect_count"] += 1
            self.incorrect_overall += 1
            self.schedule_incorrect_card(self.current_card)
        self.update_score_label()
        self.next_card()

    def check_dictee_answer(self):
        """
        In Dictee mode, compare the typed answer with the target.
        If mismatch <= allowed threshold => correct, else incorrect.
        """
        if not self.current_card:
            return

        typed_answer = self.answer_entry.get().strip()
        correct_answer = self.current_card["target"]
        mismatch = calculate_mismatch(typed_answer, correct_answer)

        if mismatch <= self.mismatch_var.get():
            # Mark correct
            self.current_card["completed"] = True
            self.correct_count += 1
            self.feedback_label.config(text="Het antwoord is goed!", fg="green")
            self.correct_answer_label.config(text="")
        else:
            # Mark incorrect
            self.current_card["incorrect_count"] += 1
            self.incorrect_overall += 1
            self.feedback_label.config(text="Het antwoord is fout!", fg="red")
            self.correct_answer_label.config(text=f"Het goede antwoord is: {correct_answer}")
            self.schedule_incorrect_card(self.current_card)

        self.update_score_label()
        self.after(1200, self.next_card)

    def next_card(self):
        """
        Fetch the next card from the queue. If empty, proceed to final queue or end.
        """
        # Clear any old feedback
        self.feedback_label.config(text="", fg="red")
        self.correct_answer_label.config(text="")

        # Clear dictee entry
        if self.learning_method_var.get() == "dictee" and hasattr(self, "answer_entry"):
            self.answer_entry.delete(0, tk.END)

        if not self.queue:
            # If main queue empty, load final queue or end
            if self.final_queue:
                self.queue = self.final_queue.copy()
                self.final_queue = []
            else:
                self.end_session()
                return

        self.current_card = self.queue.pop(0)

        # Skip a card that is already completed
        if self.current_card["completed"]:
            self.next_card()
            return

        # Show the new question
        self.question_label.config(text=self.current_card["source"])

        if self.learning_method_var.get() == "in_gedachten":
            self.answer_label.config(text="???")

    def schedule_incorrect_card(self, card):
        """
        Schedule the card for repeated testing:
        - Always reinsert it in 3–6 cards when answered wrong
        - Schedule it once at the end (only once overall)
        """
        # Always reinsert card using the 3-6 rule
        offset = random.randint(3, 6)
        insert_index = min(offset, len(self.queue))
        self.queue.insert(insert_index, card)

        # Schedule it at the end only once
        if not card["final_scheduled"]:
            card["final_scheduled"] = True
            self.final_queue.append(card)

    def update_score_label(self):
        """
        Update the "Score tot nu toe: x goed, y fout" label.
        """
        self.score_label.config(
            text=f"Score until now: {self.correct_count} correct, {self.incorrect_overall} incorrect"
        )

    def end_session(self):
        """
        Show the final score.
        Score formula:
           ( (#words correct first time) + 1/3 * (#words wrong exactly once) ) / total_words * 100%
        Provide the "Create New List" option and "Go to Home Screen" as before.
        """
        if self.session_frame:
            self.session_frame.destroy()

        # Compute custom final score:
        #  - correct_first_time: cards with incorrect_count == 0
        #  - wrong_once: cards with incorrect_count == 1
        #  - total_words = len(self.cards)
        correct_first_time = sum(1 for c in self.cards if c["incorrect_count"] == 0)
        wrong_once = sum(1 for c in self.cards if c["incorrect_count"] == 1)
        total_words = len(self.cards)

        if total_words > 0:
            raw_score = (correct_first_time + (wrong_once / 5)) / total_words * 100
        else:
            raw_score = 0

        score = round(raw_score)

        # In the special case of 69% score, select one of five short jokes.
        if score == 69:
            jokes = [
                "Nice! 69 is the best!",
                "Sixty-nine, a fine time!",
                "Keep calm – it’s 69!",
                "69: You’re on fire!",
                "Rock that 69 score!"
            ]
            message = random.choice(jokes)
        else:
            if score < 10:
                message = "Nevermind bro, maybe its better to do something else"
            elif score < 30:
                message = "Sit tight, this is a heavy sesh. You better dont quit on me now"
            elif score < 50:
                message = "Keep practicing, you'll get better!"
            elif score < 80:
                message = "Good job, keep it up!"
            elif score < 100:
                message = "Excellent work, you're a language master!"
            else:
                message = "Clean sheet bro, you're a language god!"

        result_text = f"Your score: {score}%\n{message}"

        self.end_frame = ttk.Frame(self, padding=20)
        self.end_frame.pack(fill="both", expand=True)

        result_label = ttk.Label(self.end_frame, text=result_text, font=("Helvetica", 18))
        result_label.pack(pady=20)

        # Frame to select 'n' for incorrectly answered words
        select_frame = ttk.Frame(self.end_frame)
        select_frame.pack(pady=10)

        ttk.Label(select_frame, text="Create new list of words with incorrect count ≥").pack(side="left", padx=5)
        self.new_list_n_var = tk.IntVar(value=1)
        n_spinbox = ttk.Spinbox(select_frame, from_=1, to=10, textvariable=self.new_list_n_var, width=3)
        n_spinbox.pack(side="left", padx=5)

        create_list_btn = ttk.Button(select_frame, text="Create New List", command=self.create_new_list)
        create_list_btn.pack(side="left", padx=10)

        # Button to go back to home screen
        home_btn = ttk.Button(self.end_frame, text="Go to Home Screen", command=self.restart)
        home_btn.pack(pady=20)

    def create_new_list(self):
        """
        Create a new list of words that were answered incorrectly >= n times,
        then save it as a file with the next level prefix.
        """
        n = self.new_list_n_var.get()
        # Filter the cards
        filtered_cards = [c for c in self.cards if c["incorrect_count"] >= n]

        if not filtered_cards:
            messagebox.showinfo("Info", f"No words found with incorrect_count ≥ {n}.")
            return

        # Build a DataFrame with the same columns used originally (source, target)
        source_lang = self.source_lang_var.get()
        target_lang = self.target_lang_var.get()

        new_rows = []
        for card in filtered_cards:
            new_rows.append({source_lang: card["source"], target_lang: card["target"]})
        new_df = pd.DataFrame(new_rows)

        # Generate the next level prefix
        next_level = self.level + 1
        new_filename = f"{next_level:02d}_{self.base_name}.xlsx"

        try:
            new_df.to_excel(new_filename, index=False)
            messagebox.showinfo("Success", f"Created new list:\n{new_filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not create file: {e}")

    def restart(self):
        """
        Go back to the file selection screen.
        """
        if self.end_frame:
            self.end_frame.destroy()
        self.setup_file_selection_frame()


if __name__ == "__main__":
    app = LanguageLearnerApp()
    app.mainloop()
