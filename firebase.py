# firebase.py
import firebase_admin
from firebase_admin import credentials, storage
import os
from pathlib import Path
import shutil
from datetime import datetime, timedelta

class FirebaseManager:
    """
    Gère l'initialisation et les interactions avec Firebase Storage pour la sauvegarde.
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

    def backup_directory(self, local_directory_path: str, remote_folder: str = "backups") -> bool:
        """
        Compresse un dossier local et le téléverse sur Firebase Storage.
        
        :param local_directory_path: Chemin vers le dossier à sauvegarder (ex: 'MEDICALINK_DATA').
        :param remote_folder: Dossier de destination sur Firebase.
        :return: True si la sauvegarde a réussi, False sinon.
        """
        if not self.bucket:
            print("🔥 ERREUR: Firebase non initialisé. Sauvegarde annulée.")
            return False
        
        if not os.path.isdir(local_directory_path):
            print(f"🔥 ERREUR: Le dossier local n'existe pas : {local_directory_path}")
            return False

        try:
            # Créer un nom de fichier de sauvegarde unique avec la date
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            archive_name = f"backup_{timestamp}"
            
            # Utiliser shutil pour créer une archive zip
            # On sauvegarde temporairement l'archive à la racine du projet
            archive_path_without_ext = Path(archive_name)
            archive_path = shutil.make_archive(str(archive_path_without_ext), 'zip', local_directory_path)
            
            # Définir le chemin de destination sur Firebase
            remote_path = f"{remote_folder}/{os.path.basename(archive_path)}"
            
            # Téléverser le fichier
            blob = self.bucket.blob(remote_path)
            blob.upload_from_filename(archive_path)
            
            print(f"☁️ Sauvegarde '{os.path.basename(archive_path)}' téléversée vers '{remote_path}'")
            
            # Supprimer le fichier zip local après le téléversement
            os.remove(archive_path)
            
            # Nettoyer les anciennes sauvegardes (conserver les 7 dernières)
            self._cleanup_old_backups(remote_folder, keep=7)
            
            return True
        except Exception as e:
            print(f"🔥 ERREUR lors de la sauvegarde de {local_directory_path}: {e}")
            if 'archive_path' in locals() and os.path.exists(archive_path):
                os.remove(archive_path)
            return False

    def restore_latest_backup(self, local_destination_path: str, remote_folder: str = "backups") -> bool:
        """
        Télécharge la sauvegarde la plus récente et restaure le dossier local.
        
        :param local_destination_path: Le chemin où le dossier doit être restauré (ex: 'MEDICALINK_DATA').
        :param remote_folder: Le dossier sur Firebase où se trouvent les sauvegardes.
        :return: True si la restauration a réussi, False sinon.
        """
        if not self.bucket:
            print("🔥 ERREUR: Firebase non initialisé. Restauration annulée.")
            return False
            
        try:
            # Lister toutes les sauvegardes et trouver la plus récente
            blobs = list(self.bucket.list_blobs(prefix=f"{remote_folder}/"))
            if not blobs:
                print("ℹ️ Aucune sauvegarde trouvée sur Firebase.")
                return False
            
            latest_blob = max(blobs, key=lambda b: b.time_created)
            
            # Télécharger la sauvegarde la plus récente
            temp_zip_path = Path(f"temp_restore_{latest_blob.name.split('/')[-1]}")
            latest_blob.download_to_filename(str(temp_zip_path))
            print(f"📥 Sauvegarde la plus récente '{latest_blob.name}' téléchargée.")
            
            # Supprimer l'ancien dossier local s'il existe
            if os.path.isdir(local_destination_path):
                print(f"🗑️ Suppression de l'ancien dossier local : {local_destination_path}")
                shutil.rmtree(local_destination_path)
            
            # Décompresser l'archive à l'emplacement de destination
            print(f"🔄 Décompression de la sauvegarde vers {local_destination_path}...")
            shutil.unpack_archive(str(temp_zip_path), local_destination_path, 'zip')
            
            # Supprimer le fichier zip temporaire
            os.remove(str(temp_zip_path))
            
            print("✅ Restauration terminée avec succès.")
            return True
        except Exception as e:
            print(f"🔥 ERREUR lors de la restauration : {e}")
            if 'temp_zip_path' in locals() and os.path.exists(str(temp_zip_path)):
                os.remove(str(temp_zip_path))
            return False

    def _cleanup_old_backups(self, remote_folder: str, keep: int):
        """Supprime les sauvegardes les plus anciennes, en ne conservant que le nombre 'keep' spécifié."""
        try:
            blobs = sorted(
                list(self.bucket.list_blobs(prefix=f"{remote_folder}/")),
                key=lambda b: b.time_created,
                reverse=True
            )
            if len(blobs) > keep:
                for blob_to_delete in blobs[keep:]:
                    blob_to_delete.delete()
                    print(f"🧹 Ancienne sauvegarde supprimée : {blob_to_delete.name}")
        except Exception as e:
            print(f"🔥 ERREUR lors du nettoyage des anciennes sauvegardes : {e}")