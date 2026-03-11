import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Note: react-native-health only works on iOS with a development build
// For Android, we'll use Health Connect when available
// This service provides a unified interface for both platforms

const HEALTH_STORAGE_KEY = '@health_data';

export interface HealthData {
  steps: number;
  calories: number;
  activeMinutes: number;
  distance: number; // in km
  lastSynced: string | null;
}

export interface HealthPermissions {
  steps: boolean;
  calories: boolean;
  activeEnergy: boolean;
  distance: boolean;
  workouts: boolean;
}

let AppleHealthKit: any = null;

// Dynamic import for iOS only
if (Platform.OS === 'ios') {
  try {
    AppleHealthKit = require('react-native-health').default;
  } catch (e) {
    console.log('Apple HealthKit not available:', e);
  }
}

const healthKitPermissions = {
  permissions: {
    read: [
      'StepCount',
      'ActiveEnergyBurned',
      'BasalEnergyBurned',
      'DistanceWalkingRunning',
      'Workout',
    ],
    write: [
      'ActiveEnergyBurned',
      'Workout',
    ],
  },
};

export async function isHealthAvailable(): Promise<boolean> {
  if (Platform.OS === 'ios' && AppleHealthKit) {
    return new Promise((resolve) => {
      AppleHealthKit.isAvailable((error: any, available: boolean) => {
        resolve(!error && available);
      });
    });
  }
  // Android Health Connect check would go here
  return false;
}

export async function requestHealthPermissions(): Promise<boolean> {
  if (Platform.OS === 'ios' && AppleHealthKit) {
    return new Promise((resolve) => {
      AppleHealthKit.initHealthKit(healthKitPermissions, (error: any) => {
        if (error) {
          console.log('HealthKit permission error:', error);
          resolve(false);
        } else {
          resolve(true);
        }
      });
    });
  }
  return false;
}

export async function getTodaySteps(): Promise<number> {
  if (Platform.OS !== 'ios' || !AppleHealthKit) {
    const stored = await getStoredHealthData();
    return stored.steps;
  }

  return new Promise((resolve) => {
    const options = {
      date: new Date().toISOString(),
      includeManuallyAdded: true,
    };

    AppleHealthKit.getStepCount(options, (error: any, results: any) => {
      if (error) {
        console.log('Error getting steps:', error);
        resolve(0);
      } else {
        resolve(Math.round(results?.value || 0));
      }
    });
  });
}

export async function getTodayCaloriesBurned(): Promise<number> {
  if (Platform.OS !== 'ios' || !AppleHealthKit) {
    const stored = await getStoredHealthData();
    return stored.calories;
  }

  return new Promise((resolve) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const options = {
      startDate: today.toISOString(),
      endDate: new Date().toISOString(),
    };

    AppleHealthKit.getActiveEnergyBurned(options, (error: any, results: any) => {
      if (error) {
        console.log('Error getting calories:', error);
        resolve(0);
      } else {
        const total = results?.reduce((sum: number, r: any) => sum + (r.value || 0), 0) || 0;
        resolve(Math.round(total));
      }
    });
  });
}

export async function getTodayDistance(): Promise<number> {
  if (Platform.OS !== 'ios' || !AppleHealthKit) {
    const stored = await getStoredHealthData();
    return stored.distance;
  }

  return new Promise((resolve) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const options = {
      startDate: today.toISOString(),
      endDate: new Date().toISOString(),
    };

    AppleHealthKit.getDistanceWalkingRunning(options, (error: any, results: any) => {
      if (error) {
        console.log('Error getting distance:', error);
        resolve(0);
      } else {
        // Convert meters to km
        const total = results?.reduce((sum: number, r: any) => sum + (r.value || 0), 0) || 0;
        resolve(Math.round(total / 1000 * 10) / 10);
      }
    });
  });
}

export async function syncHealthData(): Promise<HealthData> {
  const steps = await getTodaySteps();
  const calories = await getTodayCaloriesBurned();
  const distance = await getTodayDistance();
  
  const healthData: HealthData = {
    steps,
    calories,
    activeMinutes: Math.round(steps / 100), // Estimate
    distance,
    lastSynced: new Date().toISOString(),
  };
  
  await AsyncStorage.setItem(HEALTH_STORAGE_KEY, JSON.stringify(healthData));
  
  return healthData;
}

export async function getStoredHealthData(): Promise<HealthData> {
  try {
    const stored = await AsyncStorage.getItem(HEALTH_STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.log('Error reading stored health data:', e);
  }
  
  return {
    steps: 0,
    calories: 0,
    activeMinutes: 0,
    distance: 0,
    lastSynced: null,
  };
}

export async function saveWorkoutToHealth(
  workout: {
    type: string;
    startDate: Date;
    endDate: Date;
    calories: number;
  }
): Promise<boolean> {
  if (Platform.OS !== 'ios' || !AppleHealthKit) {
    return false;
  }

  return new Promise((resolve) => {
    const workoutType = mapWorkoutType(workout.type);
    
    const options = {
      type: workoutType,
      startDate: workout.startDate.toISOString(),
      endDate: workout.endDate.toISOString(),
      energyBurned: workout.calories,
    };

    AppleHealthKit.saveWorkout(options, (error: any) => {
      if (error) {
        console.log('Error saving workout:', error);
        resolve(false);
      } else {
        resolve(true);
      }
    });
  });
}

function mapWorkoutType(type: string): string {
  const mapping: { [key: string]: string } = {
    'strength': 'TraditionalStrengthTraining',
    'cardio': 'Running',
    'hiit': 'HighIntensityIntervalTraining',
    'yoga': 'Yoga',
    'cycling': 'Cycling',
    'swimming': 'Swimming',
    'walking': 'Walking',
    'default': 'FunctionalStrengthTraining',
  };
  
  return mapping[type.toLowerCase()] || mapping['default'];
}

// Connection status
export async function getHealthConnectionStatus(): Promise<{
  available: boolean;
  connected: boolean;
  platform: 'apple_health' | 'health_connect' | 'none';
}> {
  const available = await isHealthAvailable();
  
  return {
    available,
    connected: available, // If available and we got here, we have permissions
    platform: Platform.OS === 'ios' ? 'apple_health' : 
              Platform.OS === 'android' ? 'health_connect' : 'none',
  };
}
