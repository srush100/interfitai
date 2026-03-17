import { useState, useEffect, useCallback } from 'react';
import { Alert, Linking, Platform } from 'react-native';
import { CustomerInfo, PurchasesOfferings, PurchasesPackage } from 'react-native-purchases';
import {
  initializeRevenueCat,
  getCustomerInfo,
  checkPremiumStatus,
  getOfferings,
  purchasePackage,
  restorePurchases,
  addCustomerInfoUpdateListener,
  getManagementURL,
  identifyUser,
  ENTITLEMENT_ID,
} from '../services/revenuecat';

interface UseSubscriptionReturn {
  isLoading: boolean;
  isPremium: boolean;
  offerings: PurchasesOfferings | null;
  currentPackage: PurchasesPackage | null;
  error: string | null;
  initialize: (userId?: string) => Promise<void>;
  purchase: (pkg: PurchasesPackage) => Promise<boolean>;
  restore: () => Promise<boolean>;
  refreshStatus: () => Promise<void>;
  openManagement: () => Promise<void>;
}

export const useSubscription = (): UseSubscriptionReturn => {
  const [isLoading, setIsLoading] = useState(true);
  const [isPremium, setIsPremium] = useState(false);
  const [offerings, setOfferings] = useState<PurchasesOfferings | null>(null);
  const [currentPackage, setCurrentPackage] = useState<PurchasesPackage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Initialize RevenueCat SDK
  const initialize = useCallback(async (userId?: string) => {
    try {
      setIsLoading(true);
      setError(null);

      // Initialize the SDK
      const success = await initializeRevenueCat(userId);
      if (!success) {
        setError('Failed to initialize subscription service');
        return;
      }

      setIsInitialized(true);

      // Fetch customer info and offerings in parallel
      const [customerInfo, availableOfferings] = await Promise.all([
        getCustomerInfo(),
        getOfferings(),
      ]);

      // Update premium status
      if (customerInfo) {
        setIsPremium(!!customerInfo.entitlements.active[ENTITLEMENT_ID]);
      }

      // Update offerings
      if (availableOfferings) {
        setOfferings(availableOfferings);
        // Set current/default package
        if (availableOfferings.current?.availablePackages?.length) {
          setCurrentPackage(availableOfferings.current.availablePackages[0]);
        }
      }
    } catch (err: any) {
      console.error('Subscription initialization error:', err);
      setError(err.message || 'Failed to initialize');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Listen for customer info updates
  useEffect(() => {
    if (!isInitialized) return;

    const unsubscribe = addCustomerInfoUpdateListener((customerInfo: CustomerInfo) => {
      setIsPremium(!!customerInfo.entitlements.active[ENTITLEMENT_ID]);
    });

    return unsubscribe;
  }, [isInitialized]);

  // Purchase a package
  const purchase = useCallback(async (pkg: PurchasesPackage): Promise<boolean> => {
    try {
      setIsLoading(true);
      setError(null);

      const result = await purchasePackage(pkg);

      if (result.error === 'cancelled') {
        // User cancelled - don't show error
        return false;
      }

      if (!result.success && result.error) {
        setError(result.error);
        Alert.alert('Purchase Failed', result.error);
        return false;
      }

      if (result.customerInfo) {
        setIsPremium(!!result.customerInfo.entitlements.active[ENTITLEMENT_ID]);
      }

      if (result.success) {
        Alert.alert(
          'Success!',
          'Thank you for subscribing to InterFitAI Premium! You now have access to all features.',
          [{ text: 'OK' }]
        );
      }

      return result.success;
    } catch (err: any) {
      console.error('Purchase error:', err);
      setError(err.message || 'Purchase failed');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Restore previous purchases
  const restore = useCallback(async (): Promise<boolean> => {
    try {
      setIsLoading(true);
      setError(null);

      const result = await restorePurchases();

      if (!result.success && result.error) {
        setError(result.error);
        Alert.alert('Restore Failed', result.error);
        return false;
      }

      if (result.customerInfo) {
        setIsPremium(!!result.customerInfo.entitlements.active[ENTITLEMENT_ID]);
      }

      if (result.success) {
        Alert.alert(
          'Purchases Restored',
          'Your premium subscription has been restored!',
          [{ text: 'OK' }]
        );
      } else {
        Alert.alert(
          'No Purchases Found',
          'We could not find any previous purchases to restore.',
          [{ text: 'OK' }]
        );
      }

      return result.success;
    } catch (err: any) {
      console.error('Restore error:', err);
      setError(err.message || 'Restore failed');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Refresh subscription status
  const refreshStatus = useCallback(async () => {
    try {
      const isPremiumNow = await checkPremiumStatus();
      setIsPremium(isPremiumNow);
    } catch (err: any) {
      console.error('Refresh status error:', err);
    }
  }, []);

  // Open subscription management (App Store/Play Store)
  const openManagement = useCallback(async () => {
    try {
      const url = await getManagementURL();
      if (url) {
        await Linking.openURL(url);
      } else {
        // Fallback to platform-specific subscription management
        const fallbackUrl = Platform.OS === 'ios'
          ? 'https://apps.apple.com/account/subscriptions'
          : 'https://play.google.com/store/account/subscriptions';
        await Linking.openURL(fallbackUrl);
      }
    } catch (err: any) {
      console.error('Failed to open management URL:', err);
      Alert.alert('Error', 'Could not open subscription management');
    }
  }, []);

  return {
    isLoading,
    isPremium,
    offerings,
    currentPackage,
    error,
    initialize,
    purchase,
    restore,
    refreshStatus,
    openManagement,
  };
};

export default useSubscription;
