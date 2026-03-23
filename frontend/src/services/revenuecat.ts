import { Platform } from 'react-native';
import Purchases, { 
  LOG_LEVEL, 
  CustomerInfo,
  PurchasesOfferings,
  PurchasesPackage,
  PURCHASES_ERROR_CODE,
} from 'react-native-purchases';

// RevenueCat API Keys
const REVENUECAT_APPLE_KEY = 'appl_ncuQwkBBIyQCXaXaPDOXvNUtwCe';
const REVENUECAT_GOOGLE_KEY = 'goog_JeyjcBbgdxcRRybZEMfFrIPXGRo';

// Entitlement ID - this should match what's configured in RevenueCat dashboard
export const ENTITLEMENT_ID = 'premium';

// Check if RevenueCat is available (only on native platforms)
const isRevenueCatAvailable = Platform.OS !== 'web';

// Initialize RevenueCat SDK
export const initializeRevenueCat = async (userId?: string): Promise<boolean> => {
  if (!isRevenueCatAvailable) {
    console.log('RevenueCat not available on web platform');
    return false;
  }

  try {
    // Enable verbose logging in development
    if (__DEV__) {
      Purchases.setLogLevel(LOG_LEVEL.VERBOSE);
    }

    // Get platform-specific API key
    const apiKey = Platform.OS === 'ios' ? REVENUECAT_APPLE_KEY : REVENUECAT_GOOGLE_KEY;

    // Configure the SDK
    await Purchases.configure({
      apiKey,
      appUserID: userId || null,
    });

    console.log('RevenueCat initialized successfully');
    return true;
  } catch (error) {
    console.error('Failed to initialize RevenueCat:', error);
    return false;
  }
};

// Set or update the user ID (call after login)
export const identifyUser = async (userId: string): Promise<CustomerInfo | null> => {
  if (!isRevenueCatAvailable) return null;
  
  try {
    const { customerInfo } = await Purchases.logIn(userId);
    return customerInfo;
  } catch (error) {
    console.error('Failed to identify user:', error);
    return null;
  }
};

// Get current customer info (subscription status)
export const getCustomerInfo = async (): Promise<CustomerInfo | null> => {
  if (!isRevenueCatAvailable) return null;
  
  try {
    const customerInfo = await Purchases.getCustomerInfo();
    return customerInfo;
  } catch (error) {
    console.error('Failed to get customer info:', error);
    return null;
  }
};

// Check if user has premium access
export const checkPremiumStatus = async (): Promise<boolean> => {
  if (!isRevenueCatAvailable) return false;
  
  try {
    const customerInfo = await Purchases.getCustomerInfo();
    return !!customerInfo.entitlements.active[ENTITLEMENT_ID];
  } catch (error) {
    console.error('Failed to check premium status:', error);
    return false;
  }
};

// Get available subscription offerings
export const getOfferings = async (): Promise<PurchasesOfferings | null> => {
  if (!isRevenueCatAvailable) return null;
  
  try {
    const offerings = await Purchases.getOfferings();
    return offerings;
  } catch (error) {
    console.error('Failed to get offerings:', error);
    return null;
  }
};

// Purchase a package
export const purchasePackage = async (
  packageToPurchase: PurchasesPackage
): Promise<{ success: boolean; customerInfo?: CustomerInfo; error?: string }> => {
  if (!isRevenueCatAvailable) {
    return { success: false, error: 'Purchases not available on web' };
  }
  
  try {
    const { customerInfo } = await Purchases.purchasePackage(packageToPurchase);
    const isPremium = !!customerInfo.entitlements.active[ENTITLEMENT_ID];
    
    return {
      success: isPremium,
      customerInfo,
    };
  } catch (error: any) {
    if (error.code === PURCHASES_ERROR_CODE.PURCHASE_CANCELLED_ERROR) {
      return { success: false, error: 'cancelled' };
    }
    
    if (error.code === PURCHASES_ERROR_CODE.PURCHASE_NOT_ALLOWED_ERROR) {
      return { success: false, error: 'Purchases not allowed on this device' };
    }
    
    if (error.code === PURCHASES_ERROR_CODE.PRODUCT_ALREADY_PURCHASED_ERROR) {
      const customerInfo = await Purchases.getCustomerInfo();
      return { success: true, customerInfo };
    }
    
    console.error('Purchase failed:', error);
    return { success: false, error: error.message || 'Purchase failed' };
  }
};

// Restore previous purchases
export const restorePurchases = async (): Promise<{ success: boolean; customerInfo?: CustomerInfo; error?: string }> => {
  if (!isRevenueCatAvailable) {
    return { success: false, error: 'Purchases not available on web' };
  }
  
  try {
    const customerInfo = await Purchases.restorePurchases();
    const isPremium = !!customerInfo.entitlements.active[ENTITLEMENT_ID];
    
    return {
      success: isPremium,
      customerInfo,
    };
  } catch (error: any) {
    console.error('Restore failed:', error);
    return { success: false, error: error.message || 'Restore failed' };
  }
};

// Add listener for customer info updates
export const addCustomerInfoUpdateListener = (
  callback: (customerInfo: CustomerInfo) => void
): (() => void) => {
  if (!isRevenueCatAvailable) {
    // Return a no-op function on web
    return () => {};
  }
  
  try {
    const listener = Purchases.addCustomerInfoUpdateListener(callback);
    return () => {
      if (listener && typeof listener.remove === 'function') {
        listener.remove();
      }
    };
  } catch (error) {
    console.error('Failed to add listener:', error);
    return () => {};
  }
};

// Get subscription management URL (for cancellation/management)
export const getManagementURL = async (): Promise<string | null> => {
  if (!isRevenueCatAvailable) return null;
  
  try {
    const customerInfo = await Purchases.getCustomerInfo();
    return customerInfo.managementURL || null;
  } catch (error) {
    console.error('Failed to get management URL:', error);
    return null;
  }
};

// Logout current user (for switching accounts)
export const logoutUser = async (): Promise<CustomerInfo | null> => {
  if (!isRevenueCatAvailable) return null;
  
  try {
    const { customerInfo } = await Purchases.logOut();
    return customerInfo;
  } catch (error) {
    console.error('Failed to logout:', error);
    return null;
  }
};

// Format price for display
export const formatPrice = (priceString: string, currencyCode: string): string => {
  return `${currencyCode} ${priceString}`;
};

// Get subscription period label
export const getSubscriptionPeriodLabel = (identifier: string): string => {
  if (identifier.includes('monthly') || identifier.includes('month')) {
    return 'Monthly';
  }
  if (identifier.includes('yearly') || identifier.includes('annual') || identifier.includes('year')) {
    return 'Yearly';
  }
  if (identifier.includes('weekly') || identifier.includes('week')) {
    return 'Weekly';
  }
  if (identifier.includes('quarterly') || identifier.includes('quarter')) {
    return 'Quarterly';
  }
  return 'Subscription';
};
