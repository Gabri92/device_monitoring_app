from django.core.management.base import BaseCommand
from django.utils import timezone
from user_devices.models import Gateway, GatewayData
from datetime import datetime, timedelta
import random
import math


class Command(BaseCommand):
    help = 'Generate 30 days of fake gateway data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to generate (default: 30)'
        )

    def handle(self, *args, **options):
        days = options['days']
        
        # Get all gateways
        gateways = Gateway.objects.all()
        if not gateways.exists():
            self.stdout.write(
                self.style.ERROR('No gateways found. Please create at least one gateway first.')
            )
            return
        
        self.stdout.write(f'Generating {days} days of fake data for {gateways.count()} gateway(s)...')
        
        total_records = 0
        
        for gateway in gateways:
            self.stdout.write(f'Processing gateway: {gateway.name}')
            
            # Generate data for each day
            for day_offset in range(days):
                current_date = timezone.now().date() - timedelta(days=day_offset)
                
                # Generate data for each 15-minute interval of the day
                for hour in range(24):
                    for minute in [0, 15, 30, 45]:
                        # Create timestamp for this interval
                        timestamp = timezone.make_aware(
                            datetime.combine(current_date, datetime.min.time())
                        ) + timedelta(hours=hour, minutes=minute)
                        
                        # Generate realistic solar data based on time of day
                        data = self.generate_solar_data(hour, minute)
                        
                        # Create or update GatewayData record
                        gateway_data, created = GatewayData.objects.get_or_create(
                            Gateway=gateway,
                            timestamp=timestamp,
                            defaults={'data': data}
                        )
                        
                        if created:
                            total_records += 1
                            
                            # Set users if gateway has users
                            if hasattr(gateway, 'user'):
                                gateway_data.user.set(gateway.user.all())
            
            self.stdout.write(f'  Generated data for {gateway.name}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated {total_records} records of fake data!')
        )

    def generate_solar_data(self, hour, minute):
        """Generate realistic solar energy data based on time of day"""
        
        # Convert to decimal hour for calculations
        decimal_hour = hour + minute / 60.0
        
        # Solar irradiance pattern (peaks around noon)
        # Assuming daylight hours from 6 AM to 6 PM
        if 6 <= decimal_hour <= 18:
            # Normalized solar angle (0 at sunrise/sunset, 1 at noon)
            solar_angle = math.sin(math.pi * (decimal_hour - 6) / 12)
            
            # Base radiance with some randomness
            base_radiance = solar_angle * 1000  # Max 1000 W/m²
            radiance = max(0, base_radiance + random.uniform(-100, 100))
            
            # Production based on radiance (typical solar panel efficiency ~20%)
            production = radiance * 0.2 * random.uniform(0.8, 1.2)  # Max ~240 kW
            
            # Performance varies with conditions
            performance = random.uniform(75, 95) if solar_angle > 0.3 else random.uniform(60, 80)
            
            # Availability is usually high during daylight
            availability = random.uniform(95, 100)
            
        else:
            # Night time - no solar production
            radiance = 0
            production = 0
            performance = 0
            availability = random.uniform(90, 100)  # Still some availability
        
        # Add some realistic noise and variations
        production += random.uniform(-10, 10)
        performance += random.uniform(-5, 5)
        availability += random.uniform(-2, 2)
        
        # Ensure values are within reasonable bounds
        production = max(0, min(500, production))  # Cap at 500 kW
        radiance = max(0, min(1400, radiance))     # Cap at 1400 W/m²
        performance = max(0, min(100, performance)) # Cap at 100%
        availability = max(0, min(100, availability)) # Cap at 100%
        
        return {
            'production': {'value': round(production, 2), 'unit': 'kW'},
            'radiance': {'value': round(radiance, 2), 'unit': 'W/m²'},
            'performance': {'value': round(performance, 2), 'unit': '%'},
            'availability': {'value': round(availability, 2), 'unit': '%'},
        }
