import type { Lang } from './api/types'

export const LANG_LABEL: Record<Lang, string> = { en: 'EN', hi: 'हिं', mr: 'मरा' }

type Dict = Record<string, Record<Lang, string>>

/** UI strings for the two phone-facing pages. Fill {placeholders} with `t(key, lang, vars)`. */
export const STRINGS: Dict = {
  consentTitle: { en: 'Your consent', hi: 'आपकी सहमति', mr: 'तुमची संमती' },
  hello: { en: 'Hello {name}', hi: 'नमस्ते {name} जी', mr: 'नमस्कार {name}' },
  intro: {
    en: 'To assess your {product} loan, TVS Credit would like to look at the records below. You decide what to share.',
    hi: 'आपके {product} लोन के आकलन के लिए TVS Credit नीचे दिए रिकॉर्ड देखना चाहता है। क्या साझा करना है, यह आप तय करें।',
    mr: 'तुमच्या {product} कर्जाच्या मूल्यांकनासाठी TVS Credit ला खालील नोंदी पाहायच्या आहेत. काय शेअर करायचे ते तुम्ही ठरवा.',
  },
  aa: { en: 'Bank statement', hi: 'बैंक स्टेटमेंट', mr: 'बँक स्टेटमेंट' },
  aaDesc: {
    en: "Money in and out of your bank account and your balance (via Account Aggregator). UPI payments show up here too.",
    hi: 'आपके बैंक खाते में आया-गया पैसा और बैलेंस (अकाउंट एग्रीगेटर के ज़रिए)। UPI भुगतान भी इसी में दिखते हैं।',
    mr: 'तुमच्या बँक खात्यातील येणारे-जाणारे पैसे आणि शिल्लक (अकाउंट अ‍ॅग्रिगेटरद्वारे). UPI पेमेंट्सही यातच दिसतात.',
  },
  telecom: { en: 'Mobile recharge history', hi: 'मोबाइल रिचार्ज का इतिहास', mr: 'मोबाइल रिचार्जचा इतिहास' },
  telecomDesc: {
    en: 'How regularly you recharge your phone and how long you have had your number.',
    hi: 'आप फोन कितनी नियमितता से रिचार्ज करते हैं और आपका नंबर कितना पुराना है।',
    mr: 'तुम्ही फोन किती नियमितपणे रिचार्ज करता आणि तुमचा नंबर किती जुना आहे.',
  },
  business: { en: 'Business records', hi: 'व्यापार रिकॉर्ड', mr: 'व्यवसाय नोंदी' },
  businessDesc: {
    en: 'GST returns (for shops) or mandi receipts (for farmers), if you have them.',
    hi: 'GST रिटर्न (दुकानदारों के लिए) या मंडी की रसीदें (किसानों के लिए), यदि हों।',
    mr: 'GST रिटर्न (दुकानदारांसाठी) किंवा मंडी पावत्या (शेतकऱ्यांसाठी), असल्यास.',
  },
  purpose: { en: 'Purpose', hi: 'उद्देश्य', mr: 'उद्देश' },
  valid: {
    en: 'Valid for {days} days. You can withdraw your consent at any time.',
    hi: '{days} दिनों तक मान्य। आप कभी भी अपनी सहमति वापस ले सकते हैं।',
    mr: '{days} दिवस वैध. तुम्ही कधीही तुमची संमती मागे घेऊ शकता.',
  },
  authorize: { en: 'I Authorize', hi: 'मैं सहमति देता/देती हूँ', mr: 'मी संमती देतो/देते' },
  deny: { en: 'No, thanks', hi: 'नहीं, धन्यवाद', mr: 'नको, धन्यवाद' },
  pickOne: { en: 'Choose at least one source to continue', hi: 'आगे बढ़ने के लिए कम से कम एक स्रोत चुनें', mr: 'पुढे जाण्यासाठी किमान एक स्रोत निवडा' },
  timer: { en: 'Link valid for {time}', hi: 'लिंक {time} तक मान्य', mr: 'लिंक {time} पर्यंत वैध' },
  thanks: { en: 'Thank you!', hi: 'धन्यवाद!', mr: 'धन्यवाद!' },
  granted: {
    en: 'Your consent is recorded. We are reviewing your application — this takes a few seconds. You will get the result on WhatsApp.',
    hi: 'आपकी सहमति दर्ज हो गई है। हम आपके आवेदन की जाँच कर रहे हैं — इसमें कुछ सेकंड लगते हैं। नतीजा आपको WhatsApp पर मिलेगा।',
    mr: 'तुमची संमती नोंदवली गेली आहे. आम्ही तुमच्या अर्जाची तपासणी करत आहोत — यास काही सेकंद लागतात. निकाल तुम्हाला WhatsApp वर मिळेल.',
  },
  denied: {
    en: 'No problem. We have not accessed any of your data.',
    hi: 'कोई बात नहीं। हमने आपका कोई भी डेटा नहीं देखा है।',
    mr: 'हरकत नाही. आम्ही तुमचा कोणताही डेटा पाहिलेला नाही.',
  },
  expired: {
    en: 'This link has expired. Please ask the dealer to start again.',
    hi: 'यह लिंक समाप्त हो चुका है। कृपया डीलर से दोबारा शुरू करने को कहें।',
    mr: 'ही लिंक कालबाह्य झाली आहे. कृपया डीलरला पुन्हा सुरू करण्यास सांगा.',
  },
  alreadyDone: {
    en: 'This consent link has already been used.',
    hi: 'यह सहमति लिंक पहले ही इस्तेमाल हो चुका है।',
    mr: 'ही संमती लिंक आधीच वापरली गेली आहे.',
  },
  notFound: {
    en: "We couldn't find this link. Please check the message you received.",
    hi: 'यह लिंक नहीं मिला। कृपया मिले हुए संदेश को जाँचें।',
    mr: 'ही लिंक सापडली नाही. कृपया मिळालेला संदेश तपासा.',
  },
  continueWa: { en: 'Continue on WhatsApp', hi: 'WhatsApp पर जारी रखें', mr: 'WhatsApp वर पुढे चला' },
  retry: { en: 'Try again', hi: 'फिर कोशिश करें', mr: 'पुन्हा प्रयत्न करा' },
  offline: {
    en: 'Could not reach the server. Please check your connection.',
    hi: 'सर्वर से संपर्क नहीं हो सका। कृपया अपना कनेक्शन जाँचें।',
    mr: 'सर्व्हरशी संपर्क होऊ शकला नाही. कृपया तुमचे कनेक्शन तपासा.',
  },
  planTitle: { en: 'Your improvement plan', hi: 'आपकी सुधार योजना', mr: 'तुमची सुधारणा योजना' },
  planFor: { en: '{product} loan', hi: '{product} लोन', mr: '{product} कर्ज' },
  step: { en: 'Step {n}', hi: 'कदम {n}', mr: 'पायरी {n}' },
  planNotFound: {
    en: 'There is no action plan for this application.',
    hi: 'इस आवेदन के लिए कोई कार्ययोजना नहीं है।',
    mr: 'या अर्जासाठी कोणतीही कृती योजना नाही.',
  },
  footerNote: { en: 'TVS Credit · Saksham', hi: 'TVS Credit · सक्षम', mr: 'TVS Credit · सक्षम' },
}

export function t(key: keyof typeof STRINGS, lang: Lang, vars: Record<string, string | number> = {}): string {
  const s = STRINGS[key]?.[lang] ?? STRINGS[key]?.en ?? String(key)
  return s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ''))
}
