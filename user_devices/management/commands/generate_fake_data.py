from django.core.management.base import BaseCommand
from django.utils import timezone
from user_devices.models import Gateway, GatewayData, Device, EnergyData, DeviceData
from datetime import datetime, timedelta
import random
import math


class Command(BaseCommand):
    help = 'Generate 30 days of fake gateway and energy meter data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to generate (default: 30)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before generating new data'
        )

    def handle(self, *args, **options):
        days = options['days']
        clear_data = options['clear']
        
        # Clear existing data if requested
        if clear_data:
            self.stdout.write('Clearing existing data...')
            gateway_data_count = GatewayData.objects.count()
            energy_data_count = EnergyData.objects.count()
            device_data_count = DeviceData.objects.count()
            
            if gateway_data_count > 0 or energy_data_count > 0 or device_data_count > 0:
                confirm = input(f'This will delete {gateway_data_count} gateway records, {energy_data_count} energy records, and {device_data_count} device records. Continue? (y/N): ')
                if confirm.lower() != 'y':
                    self.stdout.write(self.style.WARNING('Operation cancelled.'))
                    return
                
                GatewayData.objects.all().delete()
                EnergyData.objects.all().delete()
                DeviceData.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {gateway_data_count} gateway records, {energy_data_count} energy records, and {device_data_count} device records.'))
            else:
                self.stdout.write('No existing data to clear.')
        
        # Get all gateways
        gateways = Gateway.objects.all()
        if not gateways.exists():
            self.stdout.write(
                self.style.ERROR('No gateways found. Please create at least one gateway first.')
            )
            return
        
        self.stdout.write(f'Generating {days} days of fake data for {gateways.count()} gateway(s)...')
        
        total_gateway_records = 0
        total_energy_records = 0
        total_device_records = 0
        
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
                        
                        # Check if data already exists for this gateway and timestamp
                        existing_data = GatewayData.objects.filter(
                            Gateway=gateway,
                            timestamp=timestamp
                        ).first()
                        
                        if existing_data:
                            # Update existing record
                            existing_data.data = data
                            existing_data.save()
                        else:
                            # Create new GatewayData record
                            gateway_data = GatewayData.objects.create(
                                Gateway=gateway,
                                timestamp=timestamp,
                                data=data
                            )
                            total_gateway_records += 1
                            
                            # Set users if gateway has users
                            if hasattr(gateway, 'user'):
                                gateway_data.user.set(gateway.user.all())
            
            self.stdout.write(f'  Generated gateway data for {gateway.name}')
        
        # Generate energy meter data
        self.stdout.write('Generating energy meter data...')
        energy_meters = Device.objects.filter(name__icontains='energy meter')
        if not energy_meters.exists():
            self.stdout.write(
                self.style.WARNING('No energy meter devices found. Please create devices with "energy meter" in the name.')
            )
        else:
            for energy_meter in energy_meters:
                self.stdout.write(f'Processing energy meter: {energy_meter.name}')
                
                # Generate energy data for each day
                for day_offset in range(days):
                    current_date = timezone.now().date() - timedelta(days=day_offset)
                    
                    # Generate data for each 15-minute interval of the day
                    for hour in range(24):
                        for minute in [0, 15, 30, 45]:
                            # Create timestamp for this interval with 15-minute shift for energy data
                            timestamp = timezone.make_aware(
                                datetime.combine(current_date, datetime.min.time())
                            ) + timedelta(hours=hour, minutes=minute + 15)
                            
                            # Generate realistic energy data based on time of day
                            energy_data = self.generate_energy_meter_data(hour, minute, day_offset)
                            
                            # Check if data already exists for this device and timestamp
                            existing_energy = EnergyData.objects.filter(
                                Gateway=energy_meter.Gateway,
                                device_name=energy_meter,
                                timestamp=timestamp
                            ).first()
                            
                            if existing_energy:
                                # Update existing record
                                existing_energy.data = energy_data
                                existing_energy.save()
                            else:
                                # Create new EnergyData record
                                energy_record = EnergyData.objects.create(
                                    Gateway=energy_meter.Gateway,
                                    device_name=energy_meter,
                                    timestamp=timestamp,
                                    data=energy_data
                                )
                                total_energy_records += 1
                                
                                # Set users if device has users
                                if hasattr(energy_meter, 'user'):
                                    energy_record.user.set(energy_meter.user.all())
                
                self.stdout.write(f'  Generated energy data for {energy_meter.name}')
        
        # Generate device data for all devices (excluding energy meters)
        self.stdout.write('Generating device data...')
        all_devices = Device.objects.exclude(name__icontains='energy meter')
        if not all_devices.exists():
            self.stdout.write(
                self.style.WARNING('No devices found (excluding energy meters).')
            )
        else:
            for device in all_devices:
                if not device.Gateway:
                    continue
                    
                self.stdout.write(f'Processing device: {device.name}')
                
                # Generate device data for each day
                for day_offset in range(days):
                    current_date = timezone.now().date() - timedelta(days=day_offset)
                    
                    # Generate data for each 15-minute interval of the day
                    for hour in range(24):
                        for minute in [0, 15, 30, 45]:
                            # Create timestamp for this interval
                            timestamp = timezone.make_aware(
                                datetime.combine(current_date, datetime.min.time())
                            ) + timedelta(hours=hour, minutes=minute)
                            
                            # Generate realistic device data based on time of day
                            device_data = self.generate_device_data(hour, minute)
                            
                            # Check if data already exists for this device and timestamp
                            existing_device_data = DeviceData.objects.filter(
                                Gateway=device.Gateway,
                                device_name=device,
                                timestamp=timestamp
                            ).first()
                            
                            if existing_device_data:
                                # Update existing record
                                existing_device_data.data = device_data
                                existing_device_data.save()
                            else:
                                # Create new DeviceData record
                                # Note: timestamp has auto_now_add=True, so we set it after creation
                                device_data_record = DeviceData.objects.create(
                                    Gateway=device.Gateway,
                                    device_name=device,
                                    data=device_data
                                )
                                # Update timestamp manually (auto_now_add doesn't allow setting during create)
                                device_data_record.timestamp = timestamp
                                device_data_record.save(update_fields=['timestamp'])
                                total_device_records += 1
                                
                                # Set users if device has users
                                if hasattr(device, 'user'):
                                    device_data_record.user.set(device.user.all())
                
                self.stdout.write(f'  Generated device data for {device.name}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated {total_gateway_records} gateway records, {total_energy_records} energy records, and {total_device_records} device records!')
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

    def generate_energy_meter_data(self, hour, minute, day_offset):
        """Generate realistic energy meter data in the required JSON format"""
        
        # Convert to decimal hour for calculations
        decimal_hour = hour + minute / 60.0
        
        # Generate timestamp for the data
        current_time = timezone.now() - timedelta(days=day_offset)
        timestamp_str = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()
        
        # Energy consumption pattern (higher during day, lower at night)
        if 6 <= decimal_hour <= 22:
            # Daytime consumption (higher)
            base_consumption = random.uniform(0.5, 2.0)  # 0.5-2.0 kWh per 15min
        else:
            # Nighttime consumption (lower)
            base_consumption = random.uniform(0.0, 0.5)  # 0-0.5 kWh per 15min
        
        # Energy production pattern (solar-like, peaks around noon)
        if 6 <= decimal_hour <= 18:
            # Solar production pattern
            solar_angle = math.sin(math.pi * (decimal_hour - 6) / 12)
            base_production = solar_angle * random.uniform(2.0, 4.0)  # 0-4 kWh per 15min
        else:
            # No production at night
            base_production = 0
        
        # Add some realistic noise
        consumption = max(0, base_consumption + random.uniform(-0.2, 0.2))
        production = max(0, base_production + random.uniform(-0.3, 0.3))
        
        # Calculate daily totals (accumulate over the day)
        # For simplicity, we'll generate realistic daily totals
        daily_consumed = random.uniform(15, 35)  # 15-35 kWh per day
        daily_produced = random.uniform(20, 50)  # 20-50 kWh per day
        
        # Weekly and monthly are typically the same as daily for this example
        # In a real implementation, these would be calculated from historical data
        weekly_consumed = daily_consumed
        weekly_produced = daily_produced
        monthly_consumed = daily_consumed
        monthly_produced = daily_produced
        
        return {
            'timestamp': timestamp_str,
            'Energy_consumed': {
                'unit': 'kWh',
                'value': round(consumption, 2)
            },
            'Energy_produced': {
                'unit': 'kWh',
                'value': round(production, 2)
            },
            'Energy_daily_consumed': {
                'unit': 'kWh',
                'value': round(daily_consumed, 2)
            },
            'Energy_daily_produced': {
                'unit': 'kWh',
                'value': round(daily_produced, 2)
            },
            'Energy_weekly_consumed': {
                'unit': 'kWh',
                'value': round(weekly_consumed, 2)
            },
            'Energy_weekly_produced': {
                'unit': 'kWh',
                'value': round(weekly_produced, 2)
            },
            'Energy_monthly_consumed': {
                'unit': 'kWh',
                'value': round(monthly_consumed, 2)
            },
            'Energy_monthly_produced': {
                'unit': 'kWh',
                'value': round(monthly_produced, 2)
            }
        }

    def generate_device_data(self, hour, minute):
        """Generate realistic device data based on time of day"""
        
        # Convert to decimal hour for calculations
        decimal_hour = hour + minute / 60.0
        
        # Solar irradiance pattern (peaks around noon) for solar devices
        if 6 <= decimal_hour <= 18:
            # Normalized solar angle (0 at sunrise/sunset, 1 at noon)
            solar_angle = math.sin(math.pi * (decimal_hour - 6) / 12)
            
            # Voltage varies slightly (typical for solar installations)
            voltage = 230 + random.uniform(-10, 10)  # 220-240V
            
            # Current based on solar production (higher during peak hours)
            base_current = solar_angle * 50  # Max 50A
            current = max(0, base_current + random.uniform(-5, 5))
            
            # Power = Voltage * Current (in kW)
            power = (voltage * current) / 1000  # Convert to kW
            power = max(0, power + random.uniform(-1, 1))
            
            # Frequency (typical grid frequency)
            frequency = 50 + random.uniform(-0.1, 0.1)  # 49.9-50.1 Hz
            
            # Temperature (higher during day)
            temperature = 25 + solar_angle * 15 + random.uniform(-2, 2)  # 25-40°C
            
        else:
            # Night time - minimal values
            voltage = 230 + random.uniform(-5, 5)
            current = random.uniform(0, 5)  # Minimal current
            power = (voltage * current) / 1000
            frequency = 50 + random.uniform(-0.05, 0.05)
            temperature = 20 + random.uniform(-2, 2)  # Cooler at night
        
        # Add some realistic noise
        voltage += random.uniform(-2, 2)
        current += random.uniform(-1, 1)
        power += random.uniform(-0.5, 0.5)
        frequency += random.uniform(-0.02, 0.02)
        temperature += random.uniform(-1, 1)
        
        # Ensure values are within reasonable bounds
        voltage = max(200, min(250, voltage))
        current = max(0, min(100, current))
        power = max(0, min(50, power))
        frequency = max(49.5, min(50.5, frequency))
        temperature = max(15, min(45, temperature))
        
        return {
            'Voltage': {'value': round(voltage, 2), 'unit': 'V'},
            'Current': {'value': round(current, 2), 'unit': 'A'},
            'Power': {'value': round(power, 2), 'unit': 'kW'},
            'Frequency': {'value': round(frequency, 2), 'unit': 'Hz'},
            'Temperature': {'value': round(temperature, 2), 'unit': '°C'},
        }
