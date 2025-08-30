# firebase.py
import firebase_admin
from firebase_admin import credentials, storage
import os
from pathlib import Path
import shutil
from datetime import datetime, timedelta

class FirebaseManager:
    """
    Gère l'initialisation et les interactions avec Firebase Storage pour la sauvegarde et la gestion de fichiers.
    """
    def __init__(self, credentials_path, project_id):
        self.bucket = None
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred, {
                    'storageBucket': f"{project_id}"
                })
            self.bucket = storage.bucket()
            print("✅ Connexion à Firebase Storage réussie.")
        except Exception as e:
            print(f"🔥 ERREUR: Impossible de se connecter à Firebase. Erreur: {e}")

    def backup_directory(self, local_directory_path: str, remote_folder: str, machine_id: str = None) -> bool:
        """
        Compresse un dossier local et le téléverse sur Firebase Storage.
        Si machine_id est fourni, un sous-dossier est créé.

        :param local_directory_path: Chemin vers le dossier à sauvegarder.
        :param remote_folder: Dossier de base sur Firebase (ex: 'daily_backups').
        :param machine_id: ID unique de la machine pour créer un sous-dossier.
        :return: True si la sauvegarde a réussi, False sinon.
        """
        if not self.bucket:
            print("🔥 ERREUR: Firebase non initialisé. Sauvegarde annulée.")
            return False
        
        if not os.path.isdir(local_directory_path):
            print(f"🔥 ERREUR: Le dossier local n'existe pas : {local_directory_path}")
            return False

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            archive_name = f"backup_{timestamp}"
            # Utilise un dossier temporaire pour l'archive pour éviter les conflits
            temp_dir = Path("./temp_archives")
            temp_dir.mkdir(exist_ok=True)
            archive_path_without_ext = temp_dir / archive_name
            
            archive_path = shutil.make_archive(str(archive_path_without_ext), 'zip', local_directory_path)
            
            # Détermine le dossier de destination en incluant le machine_id s'il est fourni
            if machine_id:
                destination_folder = f"{remote_folder}/{machine_id}"
            else:
                destination_folder = remote_folder
            
            remote_path = f"{destination_folder}/{os.path.basename(archive_path)}"
            
            blob = self.bucket.blob(remote_path)
            blob.upload_from_filename(archive_path)
            
            print(f"☁️ Sauvegarde '{os.path.basename(archive_path)}' téléversée vers '{remote_path}'")
            
            # Nettoyage de l'archive locale
            os.remove(archive_path)
            
            # Le nettoyage se fait dans le dossier de destination spécifique sur Firebase
            self._cleanup_old_backups(destination_folder, keep=7)
            
            return True
        except Exception as e:
            print(f"🔥 ERREUR lors de la sauvegarde de {local_directory_path}: {e}")
            if 'archive_path' in locals() and os.path.exists(archive_path):
                os.remove(archive_path)
            return False

    def restore_latest_backup(self, local_destination_path: str, remote_folder: str, machine_id: str = None) -> bool:
        """
        Télécharge la sauvegarde la plus récente pour une machine donnée et restaure le dossier local.
        """
        if not self.bucket:
            print("🔥 ERREUR: Firebase non initialisé. Restauration annulée.")
            return False
        
        try:
            # Construit le préfixe de recherche en fonction du machine_id
            if machine_id:
                search_prefix = f"{remote_folder}/{machine_id}/"
            else:
                search_prefix = f"{remote_folder}/"

            blobs = list(self.bucket.list_blobs(prefix=search_prefix))
            if not blobs:
                print(f"ℹ️ Aucune sauvegarde trouvée sur Firebase dans '{search_prefix}'.")
                return False
            
            latest_blob = max(blobs, key=lambda b: b.time_created)
            
            temp_zip_path = Path(f"temp_restore_{latest_blob.name.split('/')[-1]}")
            latest_blob.download_to_filename(str(temp_zip_path))
            print(f"📥 Sauvegarde la plus récente '{latest_blob.name}' téléchargée.")
            
            if os.path.isdir(local_destination_path):
                shutil.rmtree(local_destination_path)
            
            shutil.unpack_archive(str(temp_zip_path), local_destination_path, 'zip')
            
            os.remove(str(temp_zip_path))
            
            print(f"✅ Restauration terminée avec succès pour la machine {machine_id or 'générique'}.")
            return True
        except Exception as e:
            print(f"🔥 ERREUR lors de la restauration : {e}")
            if 'temp_zip_path' in locals() and os.path.exists(str(temp_zip_path)):
                os.remove(str(temp_zip_path))
            return False

    def _cleanup_old_backups(self, remote_folder_path: str, keep: int):
        """Supprime les sauvegardes les plus anciennes dans un chemin donné."""
        try:
            if not remote_folder_path.endswith('/'):
                remote_folder_path += '/'
                
            blobs = sorted(
                list(self.bucket.list_blobs(prefix=remote_folder_path)),
                key=lambda b: b.time_created,
                reverse=True
            )
            if len(blobs) > keep:
                print(f"🧹 Nettoyage des anciennes sauvegardes dans {remote_folder_path}...")
                for blob_to_delete in blobs[keep:]:
                    blob_to_delete.delete()
                    print(f"🗑️ Ancienne sauvegarde supprimée : {blob_to_delete.name}")
        except Exception as e:
            print(f"🔥 ERREUR lors du nettoyage des anciennes sauvegardes : {e}")

    # ... (Les autres fonctions : list_files, upload_file_to_storage, etc. restent inchangées)
    # --- NOUVELLES FONCTIONS DE GESTION DE STOCKAGE ---
    def list_files(self, prefix=""):
        """Liste les fichiers et dossiers (préfixes) dans un chemin donné."""
        if not self.bucket: return [], []
        
        iterator = self.bucket.list_blobs(prefix=prefix, delimiter='/')
        files = [blob for blob in iterator]
        folders = list(iterator.prefixes)
        return files, folders

    def upload_file_to_storage(self, file_stream, remote_blob_name):
        """Téléverse un fichier (stream) vers un chemin distant."""
        if not self.bucket: return False
        try:
            blob = self.bucket.blob(remote_blob_name)
            blob.upload_from_file(file_stream)
            print(f"☁️ Fichier téléversé vers {remote_blob_name}")
            return True
        except Exception as e:
            print(f"🔥 ERREUR de téléversement : {e}")
            return False

    def delete_blob(self, blob_name):
        """Supprime un fichier (blob) spécifique."""
        if not self.bucket: return False
        try:
            blob = self.bucket.blob(blob_name)
            blob.delete()
            print(f"🗑️ Fichier supprimé : {blob_name}")
            return True
        except Exception as e:
            print(f"🔥 ERREUR de suppression de blob : {e}")
            return False
            
    def delete_folder(self, folder_prefix):
        """Supprime un dossier et tout son contenu."""
        if not self.bucket: return False
        try:
            blobs = self.bucket.list_blobs(prefix=folder_prefix)
            for blob in blobs:
                blob.delete()
            print(f"🗑️ Dossier et contenu supprimés : {folder_prefix}")
            return True
        except Exception as e:
            print(f"🔥 ERREUR de suppression de dossier : {e}")
            return False

    def create_folder(self, folder_path):
        """Crée un dossier en téléversant un fichier placeholder."""
        if not self.bucket: return False
        # Assure que le chemin se termine par un /
        if not folder_path.endswith('/'):
            folder_path += '/'
        try:
            blob = self.bucket.blob(folder_path + '.placeholder')
            blob.upload_from_string('')
            print(f"📁 Dossier créé : {folder_path}")
            return True
        except Exception as e:
            print(f"🔥 ERREUR de création de dossier : {e}")
            return False
            
    def get_download_url(self, blob_name):
        """Génère une URL de téléchargement signée et temporaire pour un fichier."""
        if not self.bucket: return None
        try:
            blob = self.bucket.blob(blob_name)
            # URL valide pour 15 minutes
            return blob.generate_signed_url(timedelta(minutes=15), method='GET')
        except Exception as e:
            print(f"🔥 ERREUR de génération d'URL : {e}")
            return None