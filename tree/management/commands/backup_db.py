"""Back up the database to a timestamped file under backups/.

Supports both engines:
  - sqlite: a consistent snapshot via the sqlite3 online-backup API
  - postgres: pg_dump (must be on PATH)

Schedule it from cron, e.g. daily:
    0 3 * * *  cd /path/to/app && /path/to/venv/bin/python manage.py backup_db
"""
import datetime
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'نسخ احتياطي لقاعدة البيانات إلى مجلد backups/ (sqlite أو postgres).'

    def add_arguments(self, parser):
        parser.add_argument('--out', default=str(settings.BASE_DIR / 'backups'),
                            help='مجلد الإخراج (الافتراضي: backups/)')

    def handle(self, *args, **opts):
        out_dir = Path(opts['out'])
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        db = settings.DATABASES['default']
        engine = db['ENGINE']

        if 'sqlite' in engine:
            import sqlite3
            dest = out_dir / f'backup-{ts}.sqlite3'
            src = sqlite3.connect(str(db['NAME']))
            dst = sqlite3.connect(str(dest))
            try:
                with dst:
                    src.backup(dst)
            finally:
                src.close()
                dst.close()
        elif 'postgresql' in engine:
            dest = out_dir / f'backup-{ts}.sql'
            env = {**os.environ, 'PGPASSWORD': db.get('PASSWORD', '')}
            cmd = [
                'pg_dump',
                '-h', db.get('HOST') or 'localhost',
                '-p', str(db.get('PORT') or '5432'),
                '-U', db.get('USER') or '',
                '-d', db.get('NAME') or '',
                '-f', str(dest),
            ]
            try:
                subprocess.run(cmd, check=True, env=env)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                raise CommandError(f'فشل pg_dump: {e}')
        else:
            raise CommandError(f'محرك غير مدعوم: {engine}')

        self.stdout.write(self.style.SUCCESS(f'تم النسخ الاحتياطي: {dest}'))
