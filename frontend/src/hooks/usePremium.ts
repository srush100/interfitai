import { useState, useEffect, useCallback } from 'react';
import { Alert, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../services/api';

interface UsePremiumReturn {
  isPremium: boolean;
  isLoading: boolean;
  checkAccess: () => Promise<boolean>;
  requirePremium: (featureName?: string) => Promise<boolean>;
}

/**
 * Hook to check premium status and gate features
 * Uses backend API only (no RevenueCat on web)
 */
export const usePremium = (): UsePremiumReturn => {
  const router = useRouter();
  const [isPremium, setIsPremium] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Check premium status on mount
  useEffect(() => {
    checkAccess();
  }, []);

  // Check premium status from backend only
  const checkAccess = useCallback(async (): Promise<boolean> => {
    try {
      setIsLoading(true);
      
      const userId = await AsyncStorage.getItem('@user_id');
      if (userId) {
        try {
          const response = await api.get(`/subscription/check/${userId}`);
          const hasPremium = response.data?.has_access || false;
          setIsPremium(hasPremium);
          return hasPremium;
        } catch (error) {
          console.log('Backend subscription check failed:', error);
        }
      }
      
      setIsPremium(false);
      return false;
    } catch (error) {
      console.error('Premium check error:', error);
      setIsPremium(false);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Require premium access - shows alert and redirects to subscription if not premium
  const requirePremium = useCallback(async (featureName?: string): Promise<boolean> => {
    const hasPremium = await checkAccess();
    
    if (!hasPremium) {
      const feature = featureName || 'this feature';
      Alert.alert(
        'Premium Required',
        `${feature} is available for premium members. Subscribe to unlock all InterFitAI features.`,
        [
          { text: 'Not Now', style: 'cancel' },
          { 
            text: 'View Plans', 
            onPress: () => router.push('/subscription')
          }
        ]
      );
      return false;
    }
    
    return true;
  }, [checkAccess, router]);

  return {
    isPremium,
    isLoading,
    checkAccess,
    requirePremium,
  };
};

export default usePremium;
