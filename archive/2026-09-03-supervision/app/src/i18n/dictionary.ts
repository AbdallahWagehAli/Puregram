import type { Lang } from '@/types';

/**
 * Bilingual string dictionary. Every key carries an Arabic and English value.
 * Keep keys flat and intention-revealing; group with dotted prefixes.
 */
export interface Strings {
  ar: string;
  en: string;
}

export const dictionary = {
  'app.name': { ar: 'بيورجرام كنترول', en: 'Puregram Control' },
  'app.tagline': { ar: 'تحكّم موثوق في المحادثات', en: 'Trusted chat control' },

  'nav.dashboard': { ar: 'الرئيسية', en: 'Dashboard' },
  'nav.managed': { ar: 'الحسابات التي أديرها', en: 'Accounts I manage' },
  'nav.managers': { ar: 'من يديرونني', en: 'My managers' },
  'nav.link': { ar: 'ربط حساب', en: 'Link account' },
  'nav.settings': { ar: 'الإعدادات', en: 'Settings' },
  'nav.logout': { ar: 'تسجيل الخروج', en: 'Log out' },
  'nav.dashboardShort': { ar: 'الرئيسية', en: 'Home' },
  'nav.managedShort': { ar: 'الحسابات', en: 'Accounts' },
  'nav.managersShort': { ar: 'المشرفون', en: 'Supervisors' },
  'nav.linkShort': { ar: 'ربط', en: 'Link' },
  'nav.settingsShort': { ar: 'الإعدادات', en: 'Settings' },
  'nav.menu': { ar: 'القائمة', en: 'Menu' },
  'nav.close': { ar: 'إغلاق', en: 'Close' },

  'action.save': { ar: 'حفظ', en: 'Save' },
  'action.cancel': { ar: 'إلغاء', en: 'Cancel' },
  'action.confirm': { ar: 'تأكيد', en: 'Confirm' },
  'action.retry': { ar: 'إعادة المحاولة', en: 'Retry' },
  'action.approve': { ar: 'قبول', en: 'Approve' },
  'action.decline': { ar: 'رفض', en: 'Decline' },
  'action.remove': { ar: 'إزالة', en: 'Remove' },
  'action.unlink': { ar: 'إلغاء الربط', en: 'Unlink' },
  'action.send': { ar: 'إرسال', en: 'Send' },
  'action.add': { ar: 'إضافة', en: 'Add' },
  'action.back': { ar: 'رجوع', en: 'Back' },

  'common.loading': { ar: 'جارٍ التحميل…', en: 'Loading…' },
  'common.error': { ar: 'حدث خطأ', en: 'Something went wrong' },
  'common.none': { ar: 'لا يوجد', en: 'None' },
  'common.email': { ar: 'البريد الإلكتروني', en: 'Email' },
  'common.password': { ar: 'كلمة المرور', en: 'Password' },
  'common.optional': { ar: 'اختياري', en: 'optional' },
  'common.search': { ar: 'بحث', en: 'Search' },
  'common.copied': { ar: 'تم النسخ', en: 'Copied' },
  'common.copy': { ar: 'نسخ', en: 'Copy' },

  'theme.toggle': { ar: 'تبديل المظهر', en: 'Toggle theme' },
  'lang.toggle': { ar: 'تبديل اللغة', en: 'Toggle language' },

  // Auth
  'auth.loginTitle': { ar: 'تسجيل الدخول', en: 'Sign in' },
  'auth.registerTitle': { ar: 'إنشاء حساب', en: 'Create account' },
  'auth.loginCta': { ar: 'دخول', en: 'Sign in' },
  'auth.registerCta': { ar: 'إنشاء الحساب', en: 'Create account' },
  'auth.displayName': { ar: 'الاسم المعروض', en: 'Display name' },
  'auth.noAccount': { ar: 'ليس لديك حساب؟', en: "Don't have an account?" },
  'auth.haveAccount': { ar: 'لديك حساب بالفعل؟', en: 'Already have an account?' },
  'auth.goRegister': { ar: 'أنشئ حسابًا', en: 'Create one' },
  'auth.goLogin': { ar: 'سجّل الدخول', en: 'Sign in' },
  'auth.passwordHint': { ar: '٨ أحرف على الأقل', en: 'At least 8 characters' },
  'auth.welcome': { ar: 'أهلًا بك في لوحة التحكّم', en: 'Welcome to your control panel' },
  'auth.subtitle': {
    ar: 'تحكّم في المحادثات المسموح بها — لحظيًّا وبأمان.',
    en: 'Manage allowed chats — in real time, securely.',
  },

  // Dashboard
  'dash.title': { ar: 'نظرة عامة', en: 'Overview' },
  'dash.greeting': { ar: 'مرحبًا', en: 'Welcome back' },
  'dash.statManaged': { ar: 'حسابات أديرها', en: 'Accounts I manage' },
  'dash.statManagers': { ar: 'من يديرونني', en: 'Managers over me' },
  'dash.statPending': { ar: 'طلبات واردة', en: 'Pending requests' },
  'dash.quickActions': { ar: 'إجراءات سريعة', en: 'Quick actions' },
  'dash.qaLink': { ar: 'إرسال طلب ربط', en: 'Send a link request' },
  'dash.qaManaged': { ar: 'إدارة الحسابات', en: 'Manage accounts' },
  'dash.qaRequests': { ar: 'مراجعة الطلبات', en: 'Review requests' },

  // Managed
  'managed.title': { ar: 'الحسابات التي أديرها', en: 'Accounts I manage' },
  'managed.subtitle': {
    ar: 'الحسابات التي وافقت على إدارتك لها.',
    en: 'Accounts that approved your control.',
  },
  'managed.empty': { ar: 'لا تدير أي حساب بعد.', en: 'You are not managing any account yet.' },
  'managed.emptyCta': { ar: 'أرسل طلب ربط لتبدأ.', en: 'Send a link request to get started.' },
  'managed.known': { ar: 'محادثات معروفة', en: 'Known' },
  'managed.allowed': { ar: 'مسموح بها', en: 'Allowed' },
  'managed.open': { ar: 'فتح', en: 'Open' },
  'managed.notBound': { ar: 'لم يُربط حساب تيليجرام', en: 'No Telegram account bound' },
  'managed.lastSeen': { ar: 'آخر ظهور', en: 'Last seen' },

  // Unlink requests (from accounts I supervise)
  'unlink.title': { ar: 'طلبات إلغاء الإشراف', en: 'Unlink requests' },
  'unlink.empty': { ar: 'لا توجد طلبات إلغاء إشراف.', en: 'No unlink requests.' },
  'unlink.hint': {
    ar: 'طلب هذا الحساب إنهاء إشرافك عليه.',
    en: 'This account asked to end your supervision.',
  },
  'unlink.requested': { ar: 'طلب الإلغاء', en: 'Requested' },
  'unlink.approved': { ar: 'تم إلغاء الربط', en: 'Link revoked' },
  'unlink.denied': { ar: 'تم رفض الطلب', en: 'Request denied' },
  'action.deny': { ar: 'رفض', en: 'Deny' },

  // Managed detail
  'detail.title': { ar: 'إدارة المحادثات', en: 'Chat control' },
  'detail.allowedOf': { ar: 'مسموح بها', en: 'allowed' },
  'detail.version': { ar: 'إصدار القائمة', en: 'List version' },
  'detail.toggleOn': { ar: 'مسموح', en: 'Allowed' },
  'detail.toggleOff': { ar: 'محظور', en: 'Blocked' },
  'detail.noChats': { ar: 'لا توجد محادثات معروفة بعد.', en: 'No known chats yet.' },
  'detail.noChatsHint': {
    ar: 'ستظهر المحادثات هنا بمجرد استخدام الجهاز.',
    en: 'Chats will appear here once the device is used.',
  },
  'detail.notBoundTitle': { ar: 'لا يوجد حساب تيليجرام مرتبط', en: 'No Telegram account linked' },
  'detail.notBoundHint': {
    ar: 'يجب أن يربط هذا المستخدم حساب تيليجرام أولًا.',
    en: 'This user must bind a Telegram account first.',
  },
  'detail.bulkTitle': { ar: 'إضافة محادثات دفعة واحدة', en: 'Bulk add chats' },
  'detail.bulkPlaceholder': {
    ar: 'الصق معرّفات أو روابط المحادثات، واحدة في كل سطر…',
    en: 'Paste chat IDs or links, one per line…',
  },
  'detail.bulkResult': { ar: 'تمت الإضافة', en: 'Added' },
  'detail.bulkSkipped': { ar: 'تم التخطّي', en: 'skipped' },
  'detail.unlinkTitle': { ar: 'إلغاء إدارة هذا الحساب', en: 'Stop managing this account' },
  'detail.unlinkConfirm': {
    ar: 'هل تريد إلغاء إدارتك لهذا الحساب؟',
    en: 'Stop managing this account?',
  },
  'detail.search': { ar: 'ابحث في المحادثات…', en: 'Search chats…' },
  'detail.filterAll': { ar: 'الكل', en: 'All' },
  'detail.filterAllowed': { ar: 'المسموح', en: 'Allowed' },
  'detail.filterBlocked': { ar: 'المحظور', en: 'Blocked' },
  'detail.noMatches': { ar: 'لا توجد نتائج مطابقة.', en: 'No matching chats.' },
  'detail.liveOn': { ar: 'مباشر', en: 'Live' },

  // Managers
  'managers.title': { ar: 'من يديرونني', en: 'Who manages me' },
  'managers.subtitle': {
    ar: 'الأشخاص الذين يتحكّمون في محادثاتك المسموح بها.',
    en: 'People who control your allowed chats.',
  },
  'managers.empty': { ar: 'لا أحد يديرك حاليًا.', en: 'Nobody manages you right now.' },
  'managers.since': { ar: 'منذ', en: 'Since' },
  'managers.removeConfirm': {
    ar: 'إزالة هذا المدير؟ لن يتحكّم في محادثاتك بعد الآن.',
    en: 'Remove this manager? They will no longer control your chats.',
  },
  'managers.incoming': { ar: 'طلبات واردة', en: 'Incoming requests' },
  'managers.incomingEmpty': { ar: 'لا توجد طلبات واردة.', en: 'No incoming requests.' },
  'managers.incomingHint': {
    ar: 'وافق ليسمح لهذا الشخص بإدارة محادثاتك.',
    en: 'Approve to let this person manage your chats.',
  },
  'managers.outgoing': { ar: 'طلبات صادرة', en: 'Outgoing requests' },
  'managers.outgoingEmpty': { ar: 'لا توجد طلبات صادرة.', en: 'No outgoing requests.' },
  'managers.outgoingHint': { ar: 'بانتظار الموافقة.', en: 'Awaiting approval.' },

  // Link (panel-initiated: the handset only ever sees a notification)
  'link.title': { ar: 'ربط حساب', en: 'Link an account' },
  'link.subtitle': {
    ar: 'أرسِل طلب إشراف إلى حساب تليجرام، والجهاز يوافق من الإشعار.',
    en: 'Send a supervision request to a Telegram account; the handset approves it from a notification.',
  },
  'link.formTitle': { ar: 'طلب إشراف جديد', en: 'New supervision request' },
  'link.formHint': {
    ar: 'اكتب معرّف الحساب في تليجرام — اسم المستخدم أو الرقم أو رابط t.me.',
    en: 'Enter the Telegram account: its username, numeric id, or a t.me link.',
  },
  'link.field': { ar: 'معرّف الحساب', en: 'Account identifier' },
  'link.placeholder': { ar: '@username أو 123456789', en: '@username or 123456789' },
  'link.submit': { ar: 'إرسال الطلب', en: 'Send request' },
  'link.sent': { ar: 'تم إرسال الطلب', en: 'Request sent' },
  'link.waiting': { ar: 'بانتظار موافقة الجهاز', en: 'Waiting for the handset' },
  'link.waitingFor': { ar: 'الحساب:', en: 'Account:' },
  'link.waitingHint': {
    ar: 'وصل إشعار إلى الجهاز بهذا الرمز. اطلب من صاحبه الضغط على «موافقة».',
    en: 'A notification carrying this code reached the handset. Ask its owner to tap Allow.',
  },
  'link.codeLabel': { ar: 'رمز التحقق', en: 'Verification code' },
  'link.cancelRequest': { ar: 'إلغاء الطلب', en: 'Cancel request' },
  'link.cancelled': { ar: 'تم إلغاء الطلب', en: 'Request cancelled' },
  'link.approved': { ar: 'تمّت الموافقة — الحساب مربوط الآن', en: 'Approved — the account is linked' },
  'link.expired': { ar: 'انتهت المدة', en: 'Expired' },
  'link.howTitle': { ar: 'كيف يعمل الربط؟', en: 'How linking works' },
  'link.step1': {
    ar: 'اكتب معرّف حساب تليجرام وأرسِل الطلب.',
    en: 'Enter the Telegram account and send the request.',
  },
  'link.step2': {
    ar: 'يصل إشعار إلى جهازه فيه اسمك ورمز التحقق.',
    en: 'A notification reaches their device with your name and the code.',
  },
  'link.step3': {
    ar: 'بمجرّد الموافقة تتحكّم في محادثاته من هنا.',
    en: 'Once they allow it, you control their chats from here.',
  },
  'link.note': {
    ar: 'لا يظهر أي رمز داخل التطبيق — الإشعار فقط. ولا يتمّ أي ربط دون موافقة من الجهاز نفسه.',
    en: 'No code is ever shown inside the app — only the notification. And nothing links without the handset approving it.',
  },

  // Settings
  'settings.title': { ar: 'الإعدادات', en: 'Settings' },
  'settings.profile': { ar: 'الملف الشخصي', en: 'Profile' },
  'settings.appearance': { ar: 'المظهر واللغة', en: 'Appearance & language' },
  'settings.telegram': { ar: 'حساب تيليجرام', en: 'Telegram account' },
  'settings.security': { ar: 'الأمان', en: 'Security' },
  'settings.shareCode': { ar: 'رمز المشاركة', en: 'Share code' },
  'settings.shareCodeHint': {
    ar: 'شارك هذا الرمز ليطلب أحدهم إدارة حسابك.',
    en: 'Share this code so someone can request to manage you.',
  },
  'settings.language': { ar: 'اللغة', en: 'Language' },
  'settings.theme': { ar: 'المظهر', en: 'Theme' },
  'settings.themeDark': { ar: 'داكن', en: 'Dark' },
  'settings.themeLight': { ar: 'فاتح', en: 'Light' },
  'settings.tgId': { ar: 'معرّف تيليجرام (رقمي)', en: 'Telegram user ID (numeric)' },
  'settings.tgBound': { ar: 'مرتبط', en: 'Bound' },
  'settings.tgVerified': { ar: 'موثّق', en: 'Verified' },
  'settings.tgUnverified': { ar: 'غير موثّق', en: 'Unverified' },
  'settings.bind': { ar: 'ربط', en: 'Bind' },
  'settings.unbind': { ar: 'إلغاء الربط', en: 'Unbind' },
  'settings.unbindConfirm': { ar: 'إلغاء ربط حساب تيليجرام؟', en: 'Unbind Telegram account?' },
  'settings.currentPassword': { ar: 'كلمة المرور الحالية', en: 'Current password' },
  'settings.newPassword': { ar: 'كلمة المرور الجديدة', en: 'New password' },
  'settings.changePassword': { ar: 'تغيير كلمة المرور', en: 'Change password' },
  'settings.saved': { ar: 'تم الحفظ', en: 'Saved' },
  'settings.passwordChanged': { ar: 'تم تغيير كلمة المرور', en: 'Password changed' },
  'settings.tgBoundMsg': { ar: 'تم ربط حساب تيليجرام', en: 'Telegram account bound' },
  'settings.tgUnboundMsg': { ar: 'تم إلغاء الربط', en: 'Telegram account unbound' },

  // Errors / validation
  'err.required': { ar: 'هذا الحقل مطلوب', en: 'This field is required' },
  'err.email': { ar: 'بريد إلكتروني غير صالح', en: 'Invalid email address' },
  'err.passwordLen': { ar: 'كلمة المرور قصيرة جدًّا', en: 'Password is too short' },
  'err.tgIdInvalid': { ar: 'معرّف غير صالح', en: 'Invalid ID' },
  'err.notFound': { ar: 'غير موجود', en: 'Not found' },
  'err.unauthorized': { ar: 'انتهت الجلسة، سجّل الدخول مجددًا', en: 'Session expired, sign in again' },
  'err.network': { ar: 'تعذّر الاتصال بالخادم', en: 'Could not reach the server' },

  // Not found route
  'route.notFound': { ar: 'الصفحة غير موجودة', en: 'Page not found' },
  'route.goHome': { ar: 'العودة للرئيسية', en: 'Back to dashboard' },
} as const satisfies Record<string, Strings>;

export type MessageKey = keyof typeof dictionary;

export function translate(key: MessageKey, lang: Lang): string {
  return dictionary[key][lang];
}
