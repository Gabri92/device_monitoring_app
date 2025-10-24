from django.core.management.base import BaseCommand
from user_devices.tasks import midnight_energy_aggregation
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test the midnight energy aggregation task'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting midnight energy aggregation test...')
        )
        
        try:
            # Execute the task directly
            midnight_energy_aggregation()
            
            self.stdout.write(
                self.style.SUCCESS('Midnight energy aggregation test completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during midnight aggregation test: {e}')
            )
            logger.error(f"Test failed: {e}")
