"""Russian for the reader-facing interface (ADR-0021).

Each key is the Turkmen text exactly as the templates and code write it; each value is its
Russian. A plural entry is a tuple of Russian's three forms: one (1, 21, 31…), few (2-4, 22-24…),
many (0, 5-20, 25…). tests/test_i18n.py fails if a Turkmen text has no Russian here, or if a
translation loses a link, a <strong> or a %(placeholder)s.

To correct a translation, edit the value, never the key. A changed Turkmen text in a template
needs its key changed here too, which the test points out.
"""

TRANSLATIONS: dict[str, str | tuple[str, ...]] = {
    # --- Every page: header, tab bar, footer (templates/base.html) --------------------------
    "Türkmen dilindäki kitaplaryň sanly kitaphanasy: gözläň, tapyň we PDF görnüşinde ýükläp alyň.":
        "Цифровая библиотека книг на туркменском языке: ищите, находите и скачивайте в PDF.",
    "<strong>Ösüş tertibi:</strong> giriş kody SMS bilen iberilmeýär, ekranda görkezilýär. Bu hakyky goragly giriş däl, saýt diňe çakylyk boýunça.":
        "<strong>Режим разработки:</strong> код входа не приходит по SMS, а показывается на экране. Это не настоящий защищённый вход, сайт открыт только по приглашению.",
    "Ösüş tertibi": "Разработка",
    "Esasy": "Основное",
    "Katalog": "Каталог",
    "Soraglar": "Запросы",
    "Dolandyryş": "Управление",
    "Hasabym": "Профиль",
    "Çykyş": "Выйти",
    "Giriş": "Вход",
    "Ýyldyz balansyňyz": "Ваш баланс звёзд",
    "Ýyldyz balansyňyz:": "Ваш баланс звёзд:",
    "Kitaphana: türkmen dilindäki kitaplaryň sanly kitaphanasy.":
        "Kitaphana — цифровая библиотека книг на туркменском языке.",
    "Bölümler": "Разделы",
    "Baş sahypa": "Главная",
    "Garaňky tertip": "Тёмная тема",
    "Ýagty ýa-da garaňky tertip": "Светлая или тёмная тема",

    # --- Search, shared by the home page, the catalogue and the 404 page ----------------------
    "Kitap gözle": "Искать книгу",
    "Kitap ýa-da awtor": "Книга или автор",
    "Gözle": "Найти",
    "Kataloga geç": "В каталог",

    # --- Home (templates/index.html) ------------------------------------------------------------
    "Kitaphana: türkmen dilindäki kitaplar": "Kitaphana — книги на туркменском языке",
    # Non-breaking spaces keep the short prepositions with their words.
    "Türkmen dilindäki kitaplar bir ýerde": "Книги на\u00a0туркменском языке в\u00a0одном месте",
    'Çat toparlarynda ýitip gidýän <span class="nowrap">PDF-ler</span> <span class="nowrap">däl-de</span>, gözläp tapyp boljak, tertipli kitaphana.':
        "Не PDF-файлы, которые теряются в чатах, а упорядоченная библиотека, где легко найти нужную книгу.",
    'Ýükläp almak üçin <a href="/login">telefon belgiňiz bilen giriň</a>: parol gerek däl.':
        'Чтобы скачивать книги, <a href="/login">войдите по номеру телефона</a>: пароль не нужен.',
    "Täze goşulanlar": "Новинки",  # both the home shelf's heading and the catalogue's sort chip
    "Ähli kitaplar": "Все книги",
    "Nähili işleýär": "Как это работает",
    "Gözläň": "Ищите",
    "Kitaby ady ýa-da awtory boýunça tapyň.": "Находите книги по названию или автору.",
    "Ýükläp alyň": "Скачивайте",
    "Käbir kitaplar mugt, käbirleri üçin ýyldyz gerek.": "Одни книги бесплатные, для других нужны звёзды.",
    "Soraň": "Запрашивайте",
    "Ýok kitaby soraň. Başgalar hem ses berse, ol öňe geçýär.":
        "Запросите книгу, которой нет. Чем больше голосов, тем выше запрос.",

    # --- Book cards and prices (templates/_macros.html) -----------------------------------------
    "%(num)d ýyldyz": ("%(num)d звезда", "%(num)d звезды", "%(num)d звёзд"),
    "Mugt": "Бесплатно",

    # --- Catalogue (templates/catalogue.html, app/catalogue.py) ---------------------------------
    "Katalog entek boş": "Каталог пока пуст",
    "Ilkinji kitaplar ýakyn wagtda goşular.": "Первые книги скоро появятся.",
    "Kitap goş": "Добавить книгу",
    "Süzgüçler": "Фильтры",
    "Dili:": "Язык:",
    "Ähli diller": "Все языки",
    "Tertibi:": "Порядок:",
    "Türkmençe": "Туркменский",
    "Rusça": "Русский",
    "Iňlisçe": "Английский",
    "Ady boýunça": "По названию",
    "«%(q)s» boýunça %(num)d kitap tapyldy": (
        "По запросу «%(q)s» найдена %(num)d книга",
        "По запросу «%(q)s» найдено %(num)d книги",
        "По запросу «%(q)s» найдено %(num)d книг",
    ),
    "%(num)d kitap": ("%(num)d книга", "%(num)d книги", "%(num)d книг"),
    "Sahypalar": "Страницы",
    "Öňki": "Назад",
    "Sahypa %(page)s / %(pages)s": "Страница %(page)s из %(pages)s",
    "Indiki": "Далее",
    "«%(q)s» boýunça kitap tapylmady": "По запросу «%(q)s» книг не найдено",
    "Başgaça ýazyp görüň. Baş we setir harplar, şeýle hem ä, ň, ş ýaly harplar gözlegde tapawutlanmaýar: «alem» ýazsaňyz, «Älem» hem tapylýar.":
        "Попробуйте написать иначе. Поиск не различает заглавные и строчные буквы, а также буквы вроде ä, ň, ş: по запросу «alem» найдётся и «Älem».",
    "Bu dilde entek kitap ýok": "Книг на этом языке пока нет",
    "Ähli kitaplara serediň": "Смотреть все книги",
    "Bu kitaby soraň": "Запросите эту книгу",
    "Kitaphanada ýok bolsa, soraň: başgalar hem goldasa, ol öňe geçýär. Adyňyz görünmeýär.":
        "Если книги нет в библиотеке, запросите её: чем больше людей поддержат запрос, тем выше он в списке. Ваше имя никто не увидит.",
    "«%(q)s» kitabyny sora": "Запросить книгу «%(q)s»",

    # --- Book page (templates/book.html) --------------------------------------------------------
    "Ýükläp almak": "Скачивание",
    "PDF ýükle (%(size)s)": "Скачать PDF (%(size)s)",
    "%(num)d ýyldyz bilen ýükle": (
        "Скачать за %(num)d звезду",
        "Скачать за %(num)d звезды",
        "Скачать за %(num)d звёзд",
    ),
    "Bu kitap mugt: ýyldyz gerek däl.": "Эта книга бесплатная: звёзды не нужны.",
    "Siz bu kitaby eýýäm satyn aldyňyz: täzeden ýüklemek mugt.":
        "Вы уже купили эту книгу: скачать её снова можно бесплатно.",
    # These three are joined on the page: "Balansyňyz 17 ýyldyz. Ýükläniňizden soň 14 ýyldyz
    # galar." and "Balansyňyz 0 ýyldyz, bu kitap üçin 5 ýyldyz gerek."
    "Balansyňyz %(num)d ýyldyz": (
        "На вашем балансе %(num)d звезда",
        "На вашем балансе %(num)d звезды",
        "На вашем балансе %(num)d звёзд",
    ),
    "Ýükläniňizden soň %(num)d ýyldyz galar.": (
        "После скачивания останется %(num)d звезда.",
        "После скачивания останется %(num)d звезды.",
        "После скачивания останется %(num)d звёзд.",
    ),
    "bu kitap üçin %(num)d ýyldyz gerek.": (
        "а для этой книги нужна %(num)d звезда.",
        "а для этой книги нужно %(num)d звезды.",
        "а для этой книги нужно %(num)d звёзд.",
    ),
    "Ýyldyzlar barada": "О звёздах",
    "Ýüklemek üçin giriň": "Войдите, чтобы скачать",
    "Diňe telefon belgiňiz gerek, parol ýok. Girenden soň şu sahypa gaýdyp gelersiňiz.":
        "Нужен только номер телефона, пароля нет. После входа вы вернётесь на эту страницу.",
    "Ýyly": "Год",
    "Dili": "Язык",
    "Sahypa": "Страниц",
    "Faýl": "Файл",
    "Bahasy": "Цена",
    "Kitap barada": "О книге",

    # --- Not enough stars (templates/insufficient_stars.html) -----------------------------------
    "Ýyldyz ýetmeýär": "Не хватает звёзд",
    "«%(title)s» kitabyny ýüklemek üçin %(num)d ýyldyz gerek.": (
        "Чтобы скачать «%(title)s», нужна %(num)d звезда.",
        "Чтобы скачать «%(title)s», нужно %(num)d звезды.",
        "Чтобы скачать «%(title)s», нужно %(num)d звёзд.",
    ),
    "Hiç zat tölenmedi we balansyňyz üýtgemedi.": "Ничего не списано, баланс не изменился.",
    "Kitabyň bahasy": "Цена книги",
    "Balansyňyz": "Ваш баланс",
    "Ýetmeýär": "Не хватает",
    "Nädip ýyldyz almaly?": "Как получить звёзды?",
    'Häzirlikçe ýyldyzlary satyn alyp bolmaýar: olary diňe administrator berýär. Administratora ýüz tutuň we telefon belgiňizi aýdyň: <strong class="nowrap">%(number)s</strong>. Ýyldyzlar goşulandan soň, şu kitaba gaýdyp geliň.':
        'Купить звёзды пока нельзя: их начисляет только администратор. Обратитесь к администратору и назовите свой номер: <strong class="nowrap">%(number)s</strong>. Когда звёзды начислят, вернитесь к этой книге.',
    "Kitaba dolan": "Вернуться к книге",

    # --- Signing in (templates/login.html, app/auth.py, app/phone.py) ---------------------------
    "Kody giriziň": "Введите код",
    "<strong>%(number)s</strong> belgisi üçin 6 sanly kod döredildi.":
        'Для номера <strong>%(number)s</strong> создан <span class="nowrap">6-значный</span> код.',
    "Telefon belgiňizi giriziň. Hasabyňyz ýok bolsa, ol şu wagt döredilýär: parol gerek däl.":
        "Введите номер телефона. Если профиля у вас ещё нет, он будет создан сейчас: пароль не нужен.",
    "<strong>Telefon belgiňizi giriziň.</strong> Türkmenistanyň islendik ykjam belgisi bolýar.":
        "<strong>Введите номер телефона.</strong> Подойдёт любой мобильный номер Туркменистана.",
    "<strong>Kody giriziň.</strong> Kod birnäçe minut işleýär we diňe bir gezek ulanylýar.":
        "<strong>Введите код.</strong> Код действует несколько минут, и использовать его можно только один раз.",
    "<strong>Boldy.</strong> Bu enjamda uzak wagtlap girilen bolup galýarsyňyz.":
        "<strong>Готово.</strong> На этом устройстве вы останетесь в профиле надолго.",
    "Ösüş tertibinde kod SMS-iň ýerine şu ýerde görkezilýär:":
        "В режиме разработки код показывается здесь вместо SMS:",
    "Kod": "Код",
    "Gir": "Войти",
    "Täze kod sora": "Запросить новый код",
    "Başga belgi bilen gir": "Войти с другим номером",
    "Telefon belgisi": "Номер телефона",
    "Kod al": "Получить код",
    "Kod 6 sanly bolmaly.": "Код должен состоять из 6 цифр.",
    "Bu kodyň möhleti gutardy ýa-da ol eýýäm ulanyldy. Täze kod soraň.":
        "Срок действия кода истёк, или он уже использован. Запросите новый код.",
    "Nädogry kod gaty köp girizildi. Täze kod soraň.":
        "Слишком много попыток с неверным кодом. Запросите новый код.",
    "Bu hasap petiklenen.": "Этот профиль заблокирован.",
    "Kod nädogry. Ýene %(num)d synanyşygyňyz galdy.": (
        "Неверный код. Осталась %(num)d попытка.",
        "Неверный код. Осталось %(num)d попытки.",
        "Неверный код. Осталось %(num)d попыток.",
    ),
    "Telefon belgiňizi giriziň.": "Введите номер телефона.",
    "Belgide diňe sanlar bolmaly, mysal üçin: +993 61 234567.":
        "В номере должны быть только цифры, например: +993 61 234567.",
    "Diňe Türkmenistanyň (+993) ykjam belgileri kabul edilýär.":
        "Принимаются только мобильные номера Туркменистана (+993).",
    "Belgi 8 sanly bolmaly (+993 goşulmazdan), mysal üçin: +993 61 234567.":
        "В номере должно быть 8 цифр (без +993), например: +993 61 234567.",
    "Bu Türkmenistanyň ykjam belgisine meňzemeýär. Belgi 6 ýa-da 71 bilen başlanmaly, mysal üçin: +993 61 234567.":
        "Это не похоже на мобильный номер Туркменистана. Номер должен начинаться с 6 или 71, например: +993 61 234567.",

    # --- Limits (app/ratelimit.py, app/downloads.py, app/requests.py) ---------------------------
    "Kod gaty köp soraldy.": "Код запрашивали слишком часто.",
    "Siz soňky wagtda gaty köp kitap ýüklediňiz.": "Вы скачали слишком много книг за короткое время.",
    "Siz soňky wagtda gaty köp sorag goşduňyz.": "Вы создали слишком много запросов за короткое время.",
    "%(num)d minutdan soň täzeden synanyşyň.": (
        "Попробуйте снова через %(num)d минуту.",
        "Попробуйте снова через %(num)d минуты.",
        "Попробуйте снова через %(num)d минут.",
    ),
    "%(num)d sagatdan soň täzeden synanyşyň.": (
        "Попробуйте снова через %(num)d час.",
        "Попробуйте снова через %(num)d часа.",
        "Попробуйте снова через %(num)d часов.",
    ),

    # --- Account and stars (templates/account.html, templates/account_history.html) -------------
    "Maglumatlar": "Данные",
    "Ýyldyz balansy": "Баланс звёзд",
    "Saýtyň dili": "Язык сайта",
    "Soňky hereketler": "Последние операции",
    "Ähli ýyldyz taryhy": "Вся история звёзд",
    "Entek hiç hili ýazgy ýok. Ýyldyz berlende ýa-da kitap ýüklände, ol şu ýerde görüner.":
        "Записей пока нет. Когда вам начислят звёзды или вы скачаете книгу, это появится здесь.",
    "Ýyldyzlarym": "Мои звёзды",
    "Balans": "Баланс",
    "Häzirki balansyňyz": "Ваш баланс",
    "ýyldyz": ("звезда", "звезды", "звёзд"),
    'Häzirlikçe ýyldyzlary satyn alyp bolmaýar: olary administrator berýär. Ýyldyz gerek bolsa, administratora ýüz tutuň we telefon belgiňizi aýdyň: <strong class="nowrap">%(number)s</strong>.':
        'Купить звёзды пока нельзя: их начисляет администратор. Если вам нужны звёзды, обратитесь к администратору и назовите свой номер: <strong class="nowrap">%(number)s</strong>.',
    "Mugt kitaplar üçin ýyldyz gerek däl. Bir gezek satyn alan kitabyňyzy täzeden mugt ýükläp bilersiňiz.":
        "Для бесплатных книг звёзды не нужны. Купленную книгу можно снова скачать бесплатно.",
    "Taryhy": "История",
    "Her ýazgy hemişe saklanýar: hiç biri pozulmaýar ýa-da üýtgedilmeýär. Ýalňyşlyk bolsa, ol täze ýazgy bilen düzedilýär.":
        "Каждая запись хранится навсегда: ни одна не удаляется и не меняется. Ошибку исправляют новой записью.",
    # The star history table (templates/_macros.html)
    "Wagty": "Время",
    "Okyjy": "Читатель",
    "Näme boldy": "Что произошло",
    "Ýyldyz": "Звёзды",
    "Galan": "Остаток",
    "Administrator berdi": "Начислил администратор",
    "Administrator düzetdi": "Исправил администратор",
    "Kitap satyn alyndy": "Книга куплена",
    "Kitap ýüklendi": "Книга скачана",
    "Ýyldyz satyn alyndy": "Звёзды куплены",
    "Yzyna gaýtaryldy": "Возвращено",

    # --- Requests (templates/requests.html, request.html, request_new.html, app/requests.py) ----
    "Kitaphanada ýok kitaplar: okyjylaryň soraglary we goldawlary.":
        "Книги, которых нет в библиотеке: запросы и голоса читателей.",
    "Kitap sora": "Запросить книгу",
    "Kitaphanada ýok kitaby soraň ýa-da başgalaryňkyny goldaň: iň köp goldananlar ilki goşulýar. Kimiň soranyny ýa-da goldanyny hiç kim görmeýär.":
        "Запросите книгу, которой нет в библиотеке, или поддержите чужой запрос: самые поддержанные добавляются первыми. Никто не видит, кто запросил или поддержал.",
    "Sanawlar": "Списки",
    "Açyk soraglar": "Открытые",
    "Tapylanlar": "Выполненные",
    "Goldanlarym": "Мои запросы",
    "%(when)s soraldy": "запрошено %(when)s",
    "Häzir açyk sorag ýok": "Открытых запросов сейчас нет",
    "Gözlän kitabyňyz kitaphanada ýok bolsa, ilkinji bolup soraň.":
        "Если нужной книги нет в библиотеке, запросите её первым.",
    "Entek tapylan sorag ýok": "Выполненных запросов пока нет",
    "Soralan kitap kitaphana goşulanda, ol şu ýerde görüner.":
        "Когда запрошенную книгу добавят в библиотеку, запрос появится здесь.",
    "Siz entek hiç bir soragy goldamadyňyz": "Вы пока не поддержали ни одного запроса",
    "Goldan ýa-da goşan soraglaryňyz şu ýerde görüner, ýapylandan soň hem.":
        "Здесь будут запросы, которые вы поддержали или создали, в том числе закрытые.",
    "«%(title)s» soragy": "Запрос «%(title)s»",
    "Okyjylaryň soragy: %(name)s.": "Запрос читателей: %(name)s.",
    "Soragyňyz goşuldy. Ol adsyz görkezilýär: kimiň soranyny hiç kim görmeýär. Başgalar goldadygyça, ol sanawda ýokary galýar.":
        "Ваш запрос добавлен. Он показан анонимно: никто не видит, кто его оставил. Чем больше людей его поддержат, тем выше он поднимется в списке.",
    "%(num)d adam goldady": (
        "поддержал %(num)d человек",
        "поддержали %(num)d человека",
        "поддержали %(num)d человек",
    ),
    "entek goldan ýok": "пока никто не поддержал",
    "Bu kitap indi kitaphanada bar.": "Эта книга теперь есть в библиотеке.",
    "«%(title)s» kitabyna geç": "Перейти к книге «%(title)s»",
    "Bu kitap kitaphana goşulypdy, ýöne häzir elýeterli däl.":
        "Эту книгу добавляли в библиотеку, но сейчас она недоступна.",
    "<strong>Bu sorag ret edildi.</strong> Sebäbi: %(reason)s":
        "<strong>Этот запрос отклонён.</strong> Причина: %(reason)s",
    "Bellik": "Примечание",
    "Goldaw": "Поддержка",
    "Bu sorag ýapyldy, indi ony goldap bolmaýar.": "Этот запрос закрыт, поддержать его больше нельзя.",
    "Goldamak üçin telefon belgiňiz bilen giriň.": "Чтобы поддержать, войдите по номеру телефона.",
    "Siz bu soragy goldadyňyz. Pikiriňizi üýtgetseňiz, ýene basyň.":
        "Вы поддержали этот запрос. Если передумаете, нажмите ещё раз.",
    "Bu kitap size hem gerek bolsa, goldaň: köp goldanan soraglar ilki goşulýar.":
        "Если эта книга нужна и вам, поддержите запрос: самые поддержанные добавляются первыми.",
    "Kitaphanada ýok kitaby soraň. Soragyňyz sanawda adsyz görkezilýär: kimiň soranyny hiç kim görmeýär. Başgalar hem goldasa, ol öňe geçýär.":
        "Запросите книгу, которой нет в библиотеке. Запрос появится в списке анонимно: никто не увидит, кто его оставил. Если его поддержат другие, он поднимется выше.",
    "Soraglara dolan": "Вернуться к запросам",
    "Bu kitaplar eýýäm bar": "Эти книги уже есть",
    "Meňzeş soraglar": "Похожие запросы",
    "Olaryň biri siziň gözleýän kitabyňyz bolsa, täze sorag goşmaň-da, ony goldaň.":
        "Если среди них есть нужная вам книга, не создавайте новый запрос, а поддержите этот.",
    "Gözleýän kitabyňyz bu ýerde ýok bolsa": "Если нужной книги здесь нет",
    "Kitabyň ady": "Название книги",
    "Awtory (hökman däl)": "Автор (необязательно)",
    "Bellik (hökman däl)": "Примечание (необязательно)",
    "Meselem: haýsy neşir, haýsy dilde. Bellik hemmä görünýär, şonuň üçin oňa adyňyzy ýazmaň.":
        "Например: какое издание, на каком языке. Примечание видят все, поэтому не пишите в нём своё имя.",
    "Hawa, täze sorag goş": "Да, создать новый запрос",
    "Soragy goş": "Отправить запрос",
    "Size sorag goşmak gadagan edildi. Kitaplary gözläp we ýükläp, beýleki soraglary bolsa goldap bilersiňiz.":
        "Вам запрещено создавать запросы. Вы можете искать и скачивать книги и поддерживать чужие запросы.",
    "Kitabyň adyny ýazyň.": "Напишите название книги.",
    "Ady %(num)d harpdan uzyn bolmaly däl.": (
        "Название должно быть не длиннее %(num)d символа.",
        "Название должно быть не длиннее %(num)d символов.",
        "Название должно быть не длиннее %(num)d символов.",
    ),
    "Awtoryň ady %(num)d harpdan uzyn bolmaly däl.": (
        "Имя автора должно быть не длиннее %(num)d символа.",
        "Имя автора должно быть не длиннее %(num)d символов.",
        "Имя автора должно быть не длиннее %(num)d символов.",
    ),
    "Bellik %(num)d harpdan uzyn bolmaly däl.": (
        "Примечание должно быть не длиннее %(num)d символа.",
        "Примечание должно быть не длиннее %(num)d символов.",
        "Примечание должно быть не длиннее %(num)d символов.",
    ),
    # The vote button (templates/_macros.html). After a count: "5 голосов. Нажмите…"
    "goldaw": ("голос", "голоса", "голосов"),
    "Goldamak üçin giriň": "Войдите, чтобы поддержать",
    "goldaw. Goldamak üçin giriň": (
        "голос. Войдите, чтобы поддержать",
        "голоса. Войдите, чтобы поддержать",
        "голосов. Войдите, чтобы поддержать",
    ),
    "Goldawyňyzy aýyryň": "Отменить поддержку",
    "Goldaň": "Поддержать",
    "goldaw. Siz goldadyňyz: aýyrmak üçin basyň": (
        "голос. Вы поддержали: нажмите, чтобы отменить",
        "голоса. Вы поддержали: нажмите, чтобы отменить",
        "голосов. Вы поддержали: нажмите, чтобы отменить",
    ),
    "goldaw. Goldamak üçin basyň": (
        "голос. Нажмите, чтобы поддержать",
        "голоса. Нажмите, чтобы поддержать",
        "голосов. Нажмите, чтобы поддержать",
    ),
    "Tapyldy": "Найдена",
    "Ret edildi": "Отклонён",

    # --- How long ago (the `ago` filter, app/templating.py) -------------------------------------
    "häzir": "только что",
    "%(num)d minut öň": ("%(num)d минуту назад", "%(num)d минуты назад", "%(num)d минут назад"),
    "%(num)d sagat öň": ("%(num)d час назад", "%(num)d часа назад", "%(num)d часов назад"),
    "%(num)d gün öň": ("%(num)d день назад", "%(num)d дня назад", "%(num)d дней назад"),
    "%(num)d hepde öň": ("%(num)d неделю назад", "%(num)d недели назад", "%(num)d недель назад"),
    "%(num)d aý öň": ("%(num)d месяц назад", "%(num)d месяца назад", "%(num)d месяцев назад"),
    "%(num)d ýyl öň": ("%(num)d год назад", "%(num)d года назад", "%(num)d лет назад"),

    # --- Not found (templates/404.html) ---------------------------------------------------------
    "Sahypa tapylmady": "Страница не найдена",
    "Bu salgyda sahypa ýok. Ol aýrylan bolmagy ýa-da salgy ýalňyş ýazylan bolmagy mümkin.":
        "По этому адресу страницы нет. Возможно, её удалили или в адресе ошибка.",

    # --- Server error (templates/500.html) ------------------------------------------------------
    "Ýalňyşlyk ýüze çykdy": "Произошла ошибка",
    "Saýtda näsazlyk boldy, bu siziň günäňiz däl. Birazdan täzeden synanyşyň.":
        "На сайте произошёл сбой, вы здесь ни при чём. Попробуйте ещё раз чуть позже.",
    "Gaýtalansa, bize şu belgini aýdyň:": "Если это повторится, сообщите нам этот код:",
}
