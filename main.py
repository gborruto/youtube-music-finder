import requests, csv, re, time, sys, os
import json
from urllib.parse import quote_plus
from datetime import datetime

API_KEY = "AIzaSyCvH1tdUWa_H9A12GC0h9VCxkllsSgzF_c"  # Sostituisci con la tua chiave
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# FILTRI ULTRA-RIGOROSI
# Parole che ESCLUDONO automaticamente il video
EXCLUDE_HARD = re.compile(r"(lyric|lyrics|visualizer|audio|teaser|shorts|remix|cover|karaoke|instrumental|acoustic|live|concert|tour|reaction|review|sub|subtitle|traduzione|italiano)", re.I)

# SOLO questi pattern sono accettati come ufficiali
OFFICIAL_STRICT = re.compile(r"(official\s*(music\s*)?video|video\s*ufficiale)", re.I)

# Canali VIETATI (troppo generici o non ufficiali)
BANNED_CHANNELS = re.compile(r"(topic|lyrics|karaoke|cover|reaction|fan|tribute|unofficial|sub|traduzione)", re.I)

def normalize_text(text: str) -> str:
    """Normalizza il testo per il confronto"""
    import unicodedata
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def extract_artist_and_title(query: str):
    """Estrae artista e titolo dalla query"""
    if ' - ' in query:
        parts = query.split(' - ', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    
    separators = [' – ', ' | ']
    for sep in separators:
        if sep in query:
            parts = query.split(sep, 1)
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip()
    
    return "", query.strip()

def is_official_channel_strict(channel_name: str, artist_name: str = "") -> bool:
    """Controllo RIGOROSO del canale - solo canali veramente ufficiali"""
    channel_lower = channel_name.lower()
    
    # VIETATI: canali generici o non ufficiali
    if BANNED_CHANNELS.search(channel_name):
        return False
    
    # ACCETTATI: canali chiaramente ufficiali
    if "vevo" in channel_lower:
        return True
    
    if "records" in channel_lower and ("official" in channel_lower or "music" in channel_lower):
        return True
        
    # Se abbiamo l'artista, il canale deve contenere il nome dell'artista
    if artist_name:
        artist_norm = normalize_text(artist_name)
        channel_norm = normalize_text(channel_name)
        
        # Il nome dell'artista deve essere nel canale
        artist_words = artist_norm.split()
        if len(artist_words) == 1:
            # Artista singolo: nome deve essere presente
            if artist_norm not in channel_norm:
                return False
        else:
            # Più parole: almeno la parola principale deve essere presente
            main_word = max(artist_words, key=len)  # Parola più lunga
            if len(main_word) > 2 and main_word not in channel_norm:
                return False
        
        # Bonus: se contiene "official" ed è dell'artista giusto
        if "official" in channel_lower:
            return True
    
    # Altrimenti rifiuta per sicurezza
    return False

def exact_title_match(video_title: str, expected_title: str) -> bool:
    """Verifica che il titolo del video contenga ESATTAMENTE il titolo del brano"""
    video_norm = normalize_text(video_title)
    title_norm = normalize_text(expected_title)
    
    if not title_norm:
        return False
    
    # Il titolo deve essere presente come sequenza completa di parole
    title_words = title_norm.split()
    
    if len(title_words) == 1:
        # Titolo di una parola: deve essere parola intera
        pattern = r'\b' + re.escape(title_norm) + r'\b'
        return bool(re.search(pattern, video_norm))
    else:
        # Titolo multi-parola: deve essere presente come frase (anche non contigua ma in ordine)
        words_found = []
        for word in title_words:
            if len(word) > 2:  # Ignora articoli/preposizioni
                pattern = r'\b' + re.escape(word) + r'\b'
                if re.search(pattern, video_norm):
                    words_found.append(word)
        
        # Almeno l'80% delle parole significative deve essere presente
        significant_words = [w for w in title_words if len(w) > 2]
        if not significant_words:
            return True  # Se non ci sono parole significative, accetta
            
        return len(words_found) >= len(significant_words) * 0.8

def is_ultra_strict_match(video_title: str, channel_name: str, expected_artist: str, expected_title: str) -> bool:
    """Controllo ULTRA-RIGOROSO - deve passare TUTTI i test"""
    
    print(f"    🔍 Test ultra-rigoroso:")
    print(f"        Video: '{video_title}'")
    print(f"        Canale: '{channel_name}'")
    
    # TEST 1: Deve contenere "official video" o "video ufficiale"
    if not OFFICIAL_STRICT.search(video_title):
        print(f"        ❌ Non contiene 'official video' o 'video ufficiale'")
        return False
    
    # TEST 2: NON deve contenere parole vietate
    if EXCLUDE_HARD.search(video_title):
        print(f"        ❌ Contiene parole vietate (lyrics, audio, live, etc.)")
        return False
    
    # TEST 3: Il canale deve essere ufficiale
    if not is_official_channel_strict(channel_name, expected_artist):
        print(f"        ❌ Canale non ufficiale o non dell'artista")
        return False
    
    # TEST 4: Il titolo del brano deve essere esatto
    if not exact_title_match(video_title, expected_title):
        print(f"        ❌ Titolo del brano non corrispondente")
        return False
    
    # TEST 5: L'artista deve essere presente nel video title
    if expected_artist:
        artist_norm = normalize_text(expected_artist)
        video_norm = normalize_text(video_title)
        
        artist_words = artist_norm.split()
        artist_found = False
        
        # Controllo nome completo
        if artist_norm in video_norm:
            artist_found = True
        else:
            # Controllo parole principali
            main_words = [w for w in artist_words if len(w) > 2]
            if main_words:
                found_words = sum(1 for w in main_words if w in video_norm)
                if found_words >= len(main_words) * 0.7:  # 70% delle parole
                    artist_found = True
        
        if not artist_found:
            print(f"        ❌ Artista non trovato nel titolo")
            return False
    
    print(f"        ✅ PASSA TUTTI I TEST - VIDEO UFFICIALE CONFERMATO")
    return True

def search_ultra_strict_official(query: str):
    """Ricerca ULTRA-RIGOROSA - solo video veramente ufficiali"""
    expected_artist, expected_title = extract_artist_and_title(query)
    
    print(f"  🎯 Ricerca ultra-rigorosa:")
    print(f"      Artista: '{expected_artist}'")
    print(f"      Titolo: '{expected_title}'")
    
    # Query molto specifica per ridurre i risultati inutili
    search_terms = []
    if expected_artist:
        search_terms.append(f'"{expected_artist}"')
    if expected_title:
        search_terms.append(f'"{expected_title}"')
    search_terms.append('"official video"')
    
    search_query = ' '.join(search_terms)
    
    params = {
        "key": API_KEY,
        "part": "snippet",
        "q": search_query,
        "type": "video",
        "maxResults": 10,  # Ridotto per risparmiare quota
        "order": "relevance"
    }
    
    try:
        print(f"  📡 Query API: {search_query}")
        r = requests.get(SEARCH_URL, params=params, timeout=15)
        
        if r.status_code == 403:
            error_data = r.json()
            error_message = error_data.get('error', {}).get('message', 'Forbidden')
            if "quota" in error_message.lower() or "exceeded" in error_message.lower():
                print("  🚫 QUOTA ESAURITA")
                return "QUOTA_EXCEEDED"
            else:
                print(f"  ❌ Errore 403: {error_message}")
                return None
                
        elif r.status_code != 200:
            print(f"  ❌ Errore API {r.status_code}")
            return None
        
        items = r.json().get("items", [])
        print(f"  📋 Ricevuti {len(items)} risultati dalla API")
        
        if not items:
            print(f"  ❌ Nessun risultato trovato")
            return None
        
        # Controlla ogni risultato con criteri ultra-rigorosi
        for i, item in enumerate(items, 1):
            snippet = item["snippet"]
            title = snippet["title"]
            channel = snippet["channelTitle"]
            video_id = item["id"]["videoId"]
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            print(f"  [{i}] '{title}' - {channel}")
            
            if is_ultra_strict_match(title, channel, expected_artist, expected_title):
                return (title, channel, url)
        
        print(f"  ❌ Nessun video passa i controlli ultra-rigorosi")
        return None
        
    except Exception as e:
        print(f"  ❌ Errore: {e}")
        return None

def load_existing_results(outfile):
    """Carica i risultati esistenti dal file CSV"""
    existing = {}
    if os.path.exists(outfile):
        try:
            with open(outfile, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    song = row.get("Richiesta", "").strip()
                    if song:
                        existing[song] = {
                            "Titolo YouTube": row.get("Titolo YouTube", ""),
                            "Canale": row.get("Canale", ""),
                            "URL": row.get("URL", ""),
                            "Status": row.get("Status", ""),
                            "Data Analisi": row.get("Data Analisi", "")
                        }
        except Exception as e:
            print(f"⚠️  Errore nel caricamento del file esistente: {e}")
    
    return existing

def get_songs_to_process(infile, existing_results):
    """Determina quali canzoni devono essere processate"""
    if not os.path.exists(infile):
        print(f"❌ File {infile} non trovato")
        return []
    
    # Prova diverse codifiche per il file di input
    encodings = ['utf-8', 'utf-8-sig', 'windows-1252', 'iso-8859-1', 'cp1252']
    all_songs = []
    
    for encoding in encodings:
        try:
            with open(infile, "r", encoding=encoding) as f:
                all_songs = [line.strip() for line in f if line.strip()]
            print(f"✅ File input letto con codifica: {encoding}")
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"⚠️  Errore lettura file input: {e}")
            continue
    else:
        print(f"❌ Impossibile leggere il file {infile}")
        return [], [], []
    
    # Filtra solo le canzoni non ancora processate
    new_songs = []
    already_processed = []
    
    for song in all_songs:
        if song in existing_results:
             status = existing_results[song].get("Status", "")
             # SOLO se è stata trovata con successo O definitivamente non trovata, salta
                if "✅ Official trovato" in status or "❌ Nessun video ufficiale" in status:
                  already_processed.append(song)
                else:
              # Riprocessa quota esaurita ed errori temporanei
              new_songs.append(song)
        else:
            new_songs.append(song)
    
    return new_songs, already_processed, all_songs

def save_complete_results(all_songs, existing_results, new_results, outfile):
    """Salva tutti i risultati (esistenti + nuovi) nel file CSV"""
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with open(outfile, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Richiesta", "Titolo YouTube", "Canale", "URL", "Status", "Data Analisi"])
        
        for song in all_songs:
            if song in new_results:
                # Usa i nuovi risultati
                row = new_results[song]
                writer.writerow([
                    song, 
                    row["Titolo YouTube"], 
                    row["Canale"], 
                    row["URL"], 
                    row["Status"], 
                    current_date
                ])
            elif song in existing_results:
                # Mantieni i risultati esistenti
                row = existing_results[song]
                writer.writerow([
                    song, 
                    row["Titolo YouTube"], 
                    row["Canale"], 
                    row["URL"], 
                    row["Status"], 
                    row["Data Analisi"]
                ])
            else:
                # Non dovrebbe mai succedere, ma per sicurezza
                writer.writerow([song, "", "", "", "❓ Non processato", ""])

def test_api_key():
    """Test preliminare API"""
    params = {
        "key": API_KEY,
        "part": "snippet",
        "q": "test official video",
        "type": "video",
        "maxResults": 1
    }
    
    try:
        r = requests.get(SEARCH_URL, params=params, timeout=10)
        if r.status_code == 403:
            error_data = r.json()
            print("❌ API key non funziona:")
            print(json.dumps(error_data, indent=2))
            return False
        elif r.status_code == 200:
            print("✅ API key OK")
            return True
        else:
            print(f"❌ Errore {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Errore test: {e}")
        return False

def main():
    print("🎵 YouTube ULTRA-STRICT Official Video Finder - MODALITÀ INCREMENTALE")
    print("=" * 70)
    print("⚡ CARATTERISTICHE:")
    print("   • Analisi incrementale: processa solo brani non ancora analizzati")
    print("   • Criterio ultra-rigoroso per video ufficiali")
    print("   • Ottimizzazione quota API con continuità tra esecuzioni")
    print("   • Mantiene storico completo dei risultati")
    print("   • Aggiunge timestamp per tracciare le analisi")
    print()
    
    # Test API
    if not test_api_key():
        print("❌ API non funziona. Controlla la chiave e le impostazioni.")
        sys.exit(1)
    
    infile = "input_songs.txt"
    outfile = "ultra_strict_results.csv"
    
    # Carica risultati esistenti
    print("📂 Caricamento risultati esistenti...")
    existing_results = load_existing_results(outfile)
    print(f"   📊 Trovati {len(existing_results)} risultati precedenti")
    
    # Determina cosa processare
    songs_to_process, already_processed, all_songs = get_songs_to_process(infile, existing_results)
    
    print(f"\n📋 STATO ANALISI:")
    print(f"   • Totale brani nel file: {len(all_songs)}")
    print(f"   • Già processati: {len(already_processed)}")
    print(f"   • Da processare oggi: {len(songs_to_process)}")
    
    if not songs_to_process:
        print("\n🎉 Tutti i brani sono già stati analizzati!")
        print(f"📄 Risultati completi in: {outfile}")
        return
    
    # Mostra alcuni esempi di cosa verrà processato
    print(f"\n🔍 Esempi di brani da analizzare oggi:")
    for i, song in enumerate(songs_to_process[:5]):
        print(f"   {i+1}. {song}")
    if len(songs_to_process) > 5:
        print(f"   ... e altri {len(songs_to_process) - 5}")
    
    input(f"\nPremi INVIO per iniziare l'analisi di {len(songs_to_process)} brani...")
    
    # Processa i nuovi brani
    new_results = {}
    success_count = 0
    quota_exceeded = False
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    print(f"\n🔍 Iniziando analisi incrementale...\n")
    
    for i, song in enumerate(songs_to_process, 1):
        print(f"[{i}/{len(songs_to_process)}] {song}")
        
        result = search_ultra_strict_official(song)
        
        if result == "QUOTA_EXCEEDED":
            quota_exceeded = True
            print(f"\n🚫 QUOTA ESAURITA dopo {i-1} nuove ricerche")
            
            # Segna le rimanenti come "quota esaurita"
            for j, remaining_song in enumerate(songs_to_process[i-1:], i):
                new_results[remaining_song] = {
                    "Titolo YouTube": "",
                    "Canale": "",
                    "URL": "",
                    "Status": "🚫 Quota esaurita",
                    "Data Analisi": current_date
                }
            break
            
        elif result:
            title, channel, url = result
            new_results[song] = {
                "Titolo YouTube": title,
                "Canale": channel,
                "URL": url,
                "Status": "✅ Official trovato",
                "Data Analisi": current_date
            }
            print(f"  🎉 SUCCESSO: Video ufficiale confermato!")
            success_count += 1
        else:
            new_results[song] = {
                "Titolo YouTube": "",
                "Canale": "",
                "URL": "",
                "Status": "❌ Nessun video ufficiale",
                "Data Analisi": current_date
            }
            print(f"  ❌ Nessun video ufficiale trovato (criterio ultra-rigoroso)")
        
        # Salvataggio periodico ogni 5 canzoni
        if i % 5 == 0:
            print(f"  💾 Salvataggio parziale...")
            save_complete_results(all_songs, existing_results, new_results, outfile)
        
        # Pausa per evitare rate limiting
        if i < len(songs_to_process) and not quota_exceeded:
            time.sleep(1.5)
        
        print()  # Riga vuota per separare
    
    # Salvataggio finale
    print("💾 Salvataggio finale...")
    save_complete_results(all_songs, existing_results, new_results, outfile)
    
    # Statistiche finali
    processed_today = len(new_results)
    total_in_db = len(existing_results) + processed_today
    total_found = len([song for song in all_songs 
                     if (song in existing_results and "✅" in existing_results[song].get("Status", "")) 
                     or (song in new_results and "✅" in new_results[song].get("Status", ""))])
    
    print(f"\n🎯 RISULTATI SESSIONE ODIERNA:")
    print(f"   📊 Nuovi brani processati: {processed_today}")
    print(f"   ✅ Nuovi video ufficiali trovati: {success_count}")
    print(f"   📄 File aggiornato: {outfile}")
    
    print(f"\n📈 STATISTICHE TOTALI:")
    print(f"   📊 Totale brani nel database: {total_in_db}/{len(all_songs)}")
    print(f"   🎬 Video ufficiali trovati: {total_found}")
    print(f"   📊 Tasso successo totale: {(total_found/total_in_db*100):.1f}%")
    
    if quota_exceeded:
        remaining = len(songs_to_process) - processed_today
        print(f"\n⚠️  Quota API esaurita. Rimangono {remaining} brani da processare.")
        print(f"   💡 Esegui di nuovo domani per continuare dall'ultima posizione!")
        print(f"   🔄 Il progresso è stato salvato automaticamente.")
    elif len(already_processed) + processed_today == len(all_songs):
        print(f"\n🎉 ANALISI COMPLETA! Tutti i brani sono stati processati.")
    
    print(f"\n💡 Prossima esecuzione: riprenderà automaticamente dai brani non processati")

if __name__ == "__main__":
    main()