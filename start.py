# ✅ CODE PYTHON COMPLET ET OPTIMISÉ (avec gestion robuste des requêtes Ollama)

import requests
import subprocess
import re
import os
import sys
import time 

# # -----------
# CONFIGURATION
# # -----------

MODEL_CHAT = "llama3"
MODEL_CODE = "codellama"

# Instructions pour Codellama (générateur de code)
SYSTEM_CODE = """
Tu es un modèle spécialisé dans la génération de code.
TON UNIQUE RÔLE :
- PRODUIS uniquement du code Python exécutable.
- Place OBLIGATOIREMENT ce code dans un bloc :
```python
# ton code ici
```
Aucun texte, aucune explication, aucun commentaire hors bloc.

Si aucun code n'est nécessaire, ne retourne RIEN.
"""

# Instructions pour Llama3 (assistant conversationnel)
SYSTEM_CHAT = """
Tu es l'assistant principal. Tu reçois :
- l'entrée utilisateur
- le code Python généré (si présent)
- la sortie exécutée du code (si présente)

Ta mission :
- Fournir une réponse claire et utile
- Utiliser les résultats du code si disponible
- Ne JAMAIS produire de code ni utiliser des balises de code.
"""

# URL de l'API Ollama
OLLAMA_URL = "http://localhost:11434/v1/chat/completions"

# Constantes pour la gestion des fichiers temporaires
CODE_FILENAME = "ollama_temp_code.py"
OUTPUT_FILENAME = "ollama_execution_output.txt"

# Paramètres de retry pour l'API Ollama
MAX_RETRIES = 2
RETRY_DELAY = 15 # Attente en secondes pour le rechargement du modèle (Augmenté à 15s)

# -----------
# FONCTIONS OLLAMA
# -----------

def ollama_generate_with_retry(model, prompt, system=None):
    """
    Tente d'appeler l'API Ollama avec une logique de retry pour gérer les 
    time-outs dus au déchargement des modèles.
    """
    messages = [{"role": "user", "content": prompt}]
    if system:
        messages.insert(0, {"role": "system", "content": system})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False 
    }
    
    for attempt in range(MAX_RETRIES):
        output = ""
        try:
            # Requête non-streaming: le client Python attend la réponse complète.
            resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
            resp.raise_for_status()
            
            data = resp.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                full_message = data["choices"][0].get("message", {})
                output = full_message.get("content", "").strip()

            # Si on reçoit un 200 OK mais la sortie est vide, on considère cela comme un échec de génération
            if not output and attempt < MAX_RETRIES - 1:
                print(f"\n[ATTENTION/RETRY] Modèle '{model}' a renvoyé une réponse vide (HTTP 200 OK). Tentative de rechargement/retry dans {RETRY_DELAY} secondes...", file=sys.stderr)
                time.sleep(RETRY_DELAY)
                continue # Passe à la tentative suivante
            
            return output

        except requests.exceptions.RequestException as e:
            error_msg = f"[Erreur Ollama] {e}"
            if attempt < MAX_RETRIES - 1:
                print(f"\n[ATTENTION/RETRY] Modèle '{model}' a échoué (Timeout/Connexion). Tentative de rechargement/retry dans {RETRY_DELAY} secondes...", file=sys.stderr)
                time.sleep(RETRY_DELAY)
                continue # Passe à la tentative suivante
            
            # Échec final
            print(f"\n--- ÉCHEC FINAL ---", file=sys.stderr)
            print(f"La requête a échoué après {MAX_RETRIES} tentatives.", file=sys.stderr)
            print("Action REQUISE: Il est FORTEMENT recommandé de définir la variable d'environnement OLLAMA_KEEP_ALIVE='-1' (ou 30m) avant de relancer 'ollama serve' pour résoudre les problèmes de timeout/déchargement du modèle.", file=sys.stderr)
            return error_msg

    return "" # Ne devrait pas être atteint

# Les autres fonctions restent inchangées 
# -----------
# EXTRAIRE LE CODE PYTHON
# -----------

def extract_python_code(text):
    """
    Extrait le code Python d'un bloc markdown ```python...```.
    """
    match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

# -----------
# EXÉCUTER LE CODE PYTHON
# -----------

def execute_python(code):
    """
    Exécute le code Python en écrivant et lisant dans des fichiers nommés.
    Ne nettoie PAS les fichiers après l'exécution pour permettre le débogage.
    """
    code_path = os.path.join(os.getcwd(), CODE_FILENAME)
    output_path = os.path.join(os.getcwd(), OUTPUT_FILENAME)
    
    # 1. Écrire le code dans le fichier
    try:
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as e:
        return f"[ERREUR] Impossible d'écrire le code dans {code_path}: {e}"

    # 2. Exécuter le code et capturer la sortie
    execution_output = ""
    try:
        result = subprocess.run(
            [sys.executable, code_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=10
        )
        
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if stderr:
            execution_output = f"[ERREUR lors de l'exécution]\n{stderr}"
        else:
            execution_output = stdout if stdout else "(Aucune sortie)"
            
        # Écrire la sortie dans le fichier pour l'historique de débogage
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(execution_output)

        return execution_output
        
    except Exception as e:
        return f"[ERREUR INCONNUE] lors de l'exécution : {e}"
    finally:
        # Les fichiers temporaires sont conservés pour le débogage, comme demandé.
        pass

# -----------
# VÉRIFICATION DES MODÈLES OLLAMA
# -----------

def check_ollama_models_status():
    """
    Vérifie si les modèles Ollama nécessaires sont chargés et répondent.
    """
    print("\n[VÉRIFICATION] Démarrage de la vérification des modèles Ollama...")
    
    models_to_check = {
        MODEL_CHAT: "Dis bonjour.", 
        MODEL_CODE: "print('Test Code')"
    }
    
    all_ok = True

    for model_name, test_prompt in models_to_check.items():
        print(f"  - Vérification du modèle '{model_name}'...", end=" ")
        try:
            result = subprocess.run(
                ["ollama", "run", model_name, test_prompt],
                capture_output=True,
                text=True,
                encoding='utf-8', 
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                print("OK.")
            elif result.returncode == 0 and not result.stdout.strip():
                if model_name == MODEL_CHAT:
                    print("AVERTISSEMENT (sortie vide). Le modèle semble chargé mais ne répond pas comme attendu.")
                    all_ok = False
                else:
                    print("OK (sortie vide ou minimale, attendu pour un modèle de code strict).")
            else:
                print(f"ÉCHEC. Code de sortie: {result.returncode}, Erreur: {result.stderr.strip()}")
                all_ok = False

        except FileNotFoundError:
            print("ERREUR: La commande 'ollama' n'a pas été trouvée. Assurez-vous qu'Ollama est installé et dans votre PATH.")
            all_ok = False
            break
        except subprocess.TimeoutExpired:
            print("ÉCHEC (Timeout). Le modèle a pris trop de temps à répondre.")
            all_ok = False
        except Exception as e:
            print(f"ERREUR INCONNUE lors de la vérification: {e}")
            all_ok = False

    if not all_ok:
        print("\n[VÉRIFICATION TERMINÉE] Un ou plusieurs modèles Ollama ne sont pas prêts.")
        print("Veuillez vous assurer qu'Ollama est démarré et que les modèles sont téléchargés (`ollama pull <modele>`).")
        print("Il est FORTEMENT recommandé de définir OLLAMA_KEEP_ALIVE='-1' avant de relancer 'ollama serve'.")
        sys.exit(1)
    
    print("\n[VÉRIFICATION TERMINÉE] Tous les modèles Ollama nécessaires semblent opérationnels.")
    time.sleep(1)

# -----------
# BOUCLE PRINCIPALE
# -----------

def main():
    """
    Fonction principale de l'assistant.
    """
    print("Assistant multi-IA (llama3 + codellama) démarré !")
    print(f"URL Ollama: {OLLAMA_URL}")
    print(f"Modèle Chat: {MODEL_CHAT} | Modèle Code: {MODEL_CODE}")
    
    # Appel de la nouvelle fonction de vérification au démarrage
    check_ollama_models_status()

    print("\nTape 'exit' pour quitter.\n")

    while True:
        try:
            user = input("user> ")
        except EOFError:
            break
        except KeyboardInterrupt:
            break

        if user.lower() == "exit":
            break

        # 1) Codellama génère du code (ou rien)
        print("ia> [codellama pense...]")
        # Utilisation de la fonction avec retry
        code_output = ollama_generate_with_retry(
            model=MODEL_CODE,
            prompt=user,
            system=SYSTEM_CODE
        )

        python_code = extract_python_code(code_output)

        execution_output = ""
        if python_code:
            print("\n# ----- CODE GÉNÉRÉ -----")
            print(python_code)
            
            print("# ----- EXÉCUTION EN COURS -----")
            # Exécution du code
            execution_output = execute_python(python_code) 
            
            print("# ----- SORTIE DU CODE -----")
            print(execution_output)

        # 2) Llama3 génère la réponse finale
        print("\nia> [llama3 pense...]")
        prompt_chat = f"""
Utilisateur : {user}

Code généré : {python_code or "[aucun]"}

Sortie du code : {execution_output or "[aucune]"}

Réponds à l'utilisateur en utilisant ces informations. """

        # Utilisation de la fonction avec retry
        final_answer = ollama_generate_with_retry(
            model=MODEL_CHAT,
            prompt=prompt_chat,
            system=SYSTEM_CHAT
        )

        print(f"\nia> {final_answer}")
        print("\n# ----------------------\n")

    print("\nAssistant terminé. Au revoir !")
    
if __name__ == "__main__":
    main()