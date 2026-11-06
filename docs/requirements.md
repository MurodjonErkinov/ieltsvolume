# IELTS Volume — kelishilgan talablar

## Mahsulot va foydalanuvchilar

IELTS Academic mock platformasi. Student pullik imtihon ishlaydi, xatolarini ko‘radi,
AI feedback oladi. Qo‘shimcha haq evaziga mentor checkup sotib olishi mumkin.
Obunalar va General Training hozirgi bosqichga kirmaydi.

Sayt tillari: o‘zbek, rus va ingliz. Imtihon savollari inglizcha qoladi;
uch til interfeys va platforma xabarlari uchun. Vaqtlar timezone bilan saqlanadi,
standart hudud `Asia/Tashkent`.

- Mehmon: homepage, platforma haqida ma’lumot, ro‘yxatdan o‘tish/kirish.
- Student: katalog, xarid, urinish va tugatilgan imtihonlar tarixi.
- Mentor: o‘ziga biriktirilgan ishlar, 12 soatlik deadline, ball va feedback.
- Admin: barcha kontent, mentorlar, narxlar, kartalar, chek tekshiruvi, access,
  foydalanuvchilar va statistika bilan yagona dashboardda ishlaydi.

Django standart User saqlanadi. Student/mentor `Profile.role` bilan, administrator
`is_staff` va tegishli permissionlar bilan aniqlanadi. Mentorlik admin huquqini bermaydi.

## Ro‘yxatdan o‘tish va parolni tiklash

Student Telegram botda o‘z telefon kontaktini ulashadi, bot bir martalik kod beradi.
Student kodni saytga kiritib username/password yaratadi. Keyingi kirish shu ma’lumotlar
orqali. Parol ham bog‘langan Telegram orqali kod bilan tiklanadi.

## Imtihon va narx

- Admin Listening, Reading, Writing, Speaking bo‘limlaridan to‘liq mock yoki alohida bo‘limli imtihon yaratadi.
- Matnlar, audio, topshiriqlar, savollar, variantlar va javob kalitlarini admin kiritadi.
- Asosiy narx AI tekshiruvi/feedbackini o‘z ichiga oladi.
- Admin imtihonga mentorni biriktiradi va checkup qo‘shimcha narxini belgilaydi.
- Student xariddan oldin mentor kimligini va yakuniy narxni ko‘radi.
- Mentor checkup tanlansa, `jami = imtihon narxi + mentor narxi`.
- Xarid narxi va mentor keyingi katalog o‘zgarishlaridan mustaqil saqlanadi.

## To‘lov va access

1. Student imtihonni va ixtiyoriy mentor checkupni tanlaydi.
2. Forma to‘lov kartasi, rekvizitlar va jami summani ko‘rsatadi.
3. Student kartaga pul o‘tkazib chek rasmini yuklaydi.
4. Vakolatli adminga sayt va Telegram bot orqali xabar keladi.
5. Admin pul tushganini qo‘lda tekshiradi; tasdiqlasa shu xaridga access beriladi.
6. Rad etilgan chek sababini student ko‘radi, to‘g‘ri chekni qayta yubora oladi.

Chek yuklanishi pul tushganining avtomatik tasdig‘i emas. Bitta xarid uchun bitta
access, boshlash muddati cheklanmagan. Bitta access faqat bitta urinish beradi.
Qayta ishlash uchun yangi xarid qilinadi.

## Imtihonni ishlash

- CD IELTSga mos navigatsiya, savol ko‘rinishi, vaqt tartibi va audio ishlashi.
- Boshlashdan oldin bir martalik urinish va zarur vaqt haqida ogohlantirish hamda tasdiq.
- Javoblar avtomatik saqlanadi; uzilish yangi urinish bermaydi.
- Qayta kirganda o‘sha urinish davom etadi; vaqt qayta boshlanmaydi.
- Server vaqtni nazorat qiladi; vaqt tugagan bo‘lim avtomatik topshiriladi.
- Speaking savollariga audio bir marta yoziladi; qayta yozish imkoniyati yo‘q.

Speakingning yozib topshirish usuli kelishilgan mock oqimidir. CD formatining savol
turlari, bo‘lim vaqtlari, audio cheklovlari va ekran holatlari imtihon oynasi bosqichida
rasmiy namunalar asosida qabul mezonlariga ajratiladi.

## Baholash va feedback

- Reading/Listening: javob kaliti orqali ball, AI orqali tushuntirish/feedback.
- Writing/Speaking: AI ball va feedback beradi.
- AI tekshiruvi topshirilgach darhol avtomatik boshlanadi. UI qayta ishlash holatini
  ko‘rsatadi; tayyor bo‘lgach natija chiqadi.
- Mentor checkup sotib olingan bo‘lsa, tanlangan mentorga sayt/bot orqali topshiriq keladi.
- Mentor xarid qilingan imtihondagi barcha bo‘limlarni tekshiradi; har biriga ball va
  ovozli yoki matnli feedback beradi. Muddat topshirilganidan boshlab 12 soat.
- AI va mentor ballari va feedbacklari alohida ko‘rsatiladi.
- To‘liq mockda overall band; alohida bo‘limli imtihonda tegishli bo‘lim ballari.

## Tugatilgan imtihonlar

Topshirilgan imtihon “Tugatgan imtihonlarim” bo‘limiga tushadi. Student javoblari,
xatolari, to‘g‘ri javoblar, ballar va feedbacklarni qayta ko‘ra oladi. Mentor feedbacki
kutilayotgan bo‘lsa holati ko‘rinadi; tayyor bo‘lgach xabar keladi.
Javoblarni qayta tahrirlash va imtihonni qayta boshlash mumkin emas.

## Amalga oshirish tartibi

1. Talablar, baza sxemasi, modellar, migratsiyalar va asosiy transaction servislar.
2. Kirish/Telegram tasdig‘i va huquqlar.
3. Admin dashboard va imtihon yaratish/publish/versionlash.
4. Student katalogi, checkout, chek tekshiruvi va bildirishnomalar.
5. CD imtihon oynasi, autosave, taymerlar, audio.
6. Avtomatik tekshiruv, AI integratsiyasi, mentor dashboardi va natijalar.
7. Homepage, interfeys tarjimalari, statistika va yakuniy tekshiruv.

Bu hujjat talablarni belgilaydi; joriy kodning tayyorlik holati
[database-schema.md](database-schema.md) va READMEda alohida ko‘rsatilgan.
