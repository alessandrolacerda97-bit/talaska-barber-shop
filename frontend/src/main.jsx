import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  AlertCircle,
  ArrowRight,
  Ban,
  Calendar,
  CircleDollarSign,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Clock,
  ExternalLink,
  Download,
  Image as ImageIcon,
  Instagram,
  LayoutDashboard,
  Lock,
  LogOut,
  MapPin,
  Menu,
  Pencil,
  Phone,
  Plus,
  RefreshCw,
  Save,
  Scissors,
  Search,
  Settings,
  ShieldCheck,
  Trash2,
  UserCog,
  Users,
  X,
} from 'lucide-react';
import { api, ApiError, query } from './api';
import './styles.css';

import logoImage from '../assets/logo-talaska.png';
import heroDesktop from '../assets/hero-reference-v4.jpg';
import heroMobile from '../assets/hero-reference-v3.jpg';
import wilianPhoto from '../assets/wilian-reference.jpg';
import moisesPhoto from '../assets/moises-reference.jpg';
import herickPhoto from '../assets/herick-reference.jpg';

const PORTFOLIO_URL = 'https://alessandro-lacerda-portfolio.onrender.com/';
const DEFAULT_WHATSAPP = '5551981201434';
const TOKEN_KEY = 'talaska_admin_access_token';
const WEEKDAYS = [
  { value: 0, label: 'Segunda-feira' },
  { value: 1, label: 'Terça-feira' },
  { value: 2, label: 'Quarta-feira' },
  { value: 3, label: 'Quinta-feira' },
  { value: 4, label: 'Sexta-feira' },
  { value: 5, label: 'Sábado' },
  { value: 6, label: 'Domingo' },
];

const fallbackServices = [
  { id: null, name: 'Corte', description: 'Cortes modernos e clássicos com acabamento impecável.', price: null, duration_minutes: 45 },
  { id: null, name: 'Barba', description: 'Modelagem e cuidados para uma barba perfeita.', price: null, duration_minutes: 30 },
  { id: null, name: 'Combo Corte + Barba', description: 'Corte e barba em uma experiência completa.', price: null, duration_minutes: 60 },
];

const fallbackBarbers = [
  { id: null, name: 'Wilian', bio: 'Cortes modernos e acabamento preciso.' },
  { id: null, name: 'Moisés', bio: 'Atendimento personalizado e cuidado em cada detalhe.' },
  { id: null, name: 'Herick', bio: 'Estilo clássico e contemporâneo.' },
];

function formatMoney(value) {
  const number = Number(value);
  if (value === null || value === undefined || Number.isNaN(number) || number <= 0) {
    return 'Valor sob consulta';
  }
  return number.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

const APPOINTMENT_STATUSES = {
  scheduled: { label: 'Agendado', tone: 'scheduled' },
  pending: { label: 'Agendado', tone: 'scheduled' },
  confirmed: { label: 'Confirmado', tone: 'confirmed' },
  completed: { label: 'Concluído', tone: 'completed' },
  cancelled: { label: 'Cancelado', tone: 'cancelled' },
  no_show: { label: 'Não compareceu', tone: 'no-show' },
};

function appointmentStatus(value) {
  return APPOINTMENT_STATUSES[value] || { label: 'Agendado', tone: 'scheduled' };
}

function formatDate(value, options = {}) {
  if (!value) return '—';
  const date = new Date(value.length === 10 ? value + 'T12:00:00' : value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    ...options,
  });
}

function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.replace('T', ' · ');
  return date.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatWeekdayShort(value) {
  const date = new Date(value + 'T12:00:00');
  return date.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '');
}

function formatMonthShort(value) {
  const date = new Date(value + 'T12:00:00');
  return date.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '');
}

function weekdayLabel(value) {
  const found = WEEKDAYS.find((weekday) => Number(weekday.value) === Number(value));
  return found ? found.label : 'Dia não definido';
}

function localDateString(offset = 0) {
  const date = new Date();
  date.setHours(12, 0, 0, 0);
  date.setDate(date.getDate() + offset);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return year + '-' + month + '-' + day;
}

function humanError(error) {
  if (error instanceof ApiError) return error.message;
  return 'Não foi possível concluir esta ação. Tente novamente.';
}

function portraitFor(barber) {
  if (barber && barber.photo_url) return barber.photo_url;
  const name = String((barber && barber.name) || '').toLowerCase();
  if (name.includes('mois')) return moisesPhoto;
  if (name.includes('herick')) return herickPhoto;
  if (name.includes('wil')) return wilianPhoto;
  return '';
}

function BarberPortrait({ barber, className = '', alt = '' }) {
  const source = portraitFor(barber);
  if (source) return <img className={className} src={source} alt={alt} loading="lazy" />;
  const initials = String(barber?.name || '?').trim().slice(0, 2).toUpperCase();
  return <span className={'barber-placeholder ' + className} aria-label={alt || 'Foto ainda não cadastrada'}>{initials}</span>;
}

function whatsappLink(phone, message) {
  return 'https://wa.me/' + String(phone || DEFAULT_WHATSAPP).replace(/\D/g, '') + '?text=' + encodeURIComponent(message);
}

function Brand({ compact = false }) {
  return (
    <a className={'brand' + (compact ? ' brand--compact' : '')} href="/" aria-label="Talaska Barber Shop — início">
      <img src={logoImage} alt="Talaska Barber Shop" />
    </a>
  );
}

function Button({ children, className = '', icon: Icon, type = 'button', ...props }) {
  return (
    <button type={type} className={'button ' + className} {...props}>
      {children}
      {Icon ? <Icon size={16} strokeWidth={2.2} aria-hidden="true" /> : null}
    </button>
  );
}

function Notice({ children, tone = 'error' }) {
  return (
    <div className={'notice notice--' + tone} role={tone === 'error' ? 'alert' : 'status'}>
      {tone === 'error' ? <AlertCircle size={18} /> : <CheckCircle size={18} />}
      <span>{children}</span>
    </div>
  );
}

function PublicHeader({ onBook, instagram }) {
  const [isOpen, setIsOpen] = useState(false);
  const links = [
    ['Início', '#inicio'],
    ['Serviços', '#servicos'],
    ['Equipe', '#equipe'],
    ['Contato', '#contato'],
  ];

  function closeMenu() {
    setIsOpen(false);
  }

  return (
    <header className="site-header">
      <Brand />
      <button className="menu-trigger" type="button" onClick={() => setIsOpen(!isOpen)} aria-expanded={isOpen} aria-label="Abrir menu">
        {isOpen ? <X size={25} /> : <Menu size={25} />}
      </button>
      <nav className={'site-nav' + (isOpen ? ' site-nav--open' : '')} aria-label="Navegação principal">
        {links.map(([label, href]) => (
          <a key={href} href={href} onClick={closeMenu}>{label}</a>
        ))}
        {instagram ? <a className="site-nav__instagram" href={instagram} target="_blank" rel="noopener noreferrer" aria-label="Instagram da Talaska Barber Shop"><Instagram size={18} /></a> : null}
        <Button className="button--gold header-book" onClick={() => { closeMenu(); onBook(); }} icon={Calendar}>
          Agendar
        </Button>
      </nav>
    </header>
  );
}

function ServiceCard({ service, onBook }) {
  return (
    <article className="service-card">
      <div className="service-card__icon"><Scissors size={31} strokeWidth={1.7} /></div>
      <h3>{service.name}</h3>
      <p>{service.description || 'Atendimento personalizado para valorizar o seu estilo.'}</p>
      <div className="service-card__meta">
        <strong>{formatMoney(service.price)}</strong>
        {service.duration_minutes ? <span>{service.duration_minutes} min</span> : null}
      </div>
      <button className="text-button" type="button" onClick={() => onBook(null, service.id)}>
        Agendar este serviço <ArrowRight size={14} />
      </button>
    </article>
  );
}

function BarberCard({ barber, onBook }) {
  return (
    <article className="barber-card">
      <BarberPortrait barber={barber} alt={'Barbeiro ' + barber.name} />
      <div className="barber-card__content">
        <h3>{barber.name}</h3>
        <p>{barber.specialties || barber.bio || 'Profissional Talaska Barber Shop'}</p>
        <button className="text-button" type="button" onClick={() => onBook(barber.id)}>
          Agendar com {barber.name} <ArrowRight size={14} />
        </button>
      </div>
    </article>
  );
}

function Footer({ settings }) {
  const whatsapp = settings.whatsapp || DEFAULT_WHATSAPP;
  const address = settings.address || 'Avenida Santa Rita, 627 · Centro';
  const instagram = settings.instagram;
  return (
    <footer id="contato" className="site-footer">
      <div className="footer-main">
        <div className="footer-contact">
          <Phone size={29} strokeWidth={1.6} />
          <div>
            <span>Telefone / WhatsApp</span>
            <a href={whatsappLink(whatsapp, 'Olá! Gostaria de falar com a Talaska Barber Shop.')}>51 98120-1434</a>
          </div>
        </div>
        <Brand compact />
        <div className="footer-contact">
          <MapPin size={30} strokeWidth={1.6} />
          <div>
            <span>Localização</span>
            <a href={'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(address)} target="_blank" rel="noopener noreferrer">{address}</a>
          </div>
        </div>
      </div>
      <div className="footer-bottom">
        <span>© {new Date().getFullYear()} Talaska Barber Shop</span>
        {instagram ? <a href={instagram} target="_blank" rel="noopener noreferrer"><Instagram size={14} /> Instagram</a> : null}
        <span>Criado por <a href={PORTFOLIO_URL} target="_blank" rel="noopener noreferrer">lacerda.dev</a></span>
      </div>
    </footer>
  );
}

function BookingModal({ close, services, barbers, presetBarberId, presetServiceId, settings }) {
  const initiallyHasService = Boolean(presetServiceId);
  const [step, setStep] = useState(initiallyHasService ? (presetBarberId ? 3 : 2) : 1);
  const [form, setForm] = useState({
    service_id: presetServiceId || null,
    barber_id: presetBarberId || null,
    appointment_date: '',
    start_time: '',
    customer_name: '',
    customer_phone: '',
    customer_email: '',
    notes: '',
  });
  const [slots, setSlots] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmation, setConfirmation] = useState(null);
  const [barberLocked, setBarberLocked] = useState(Boolean(presetBarberId));

  const selectedService = services.find((service) => Number(service.id) === Number(form.service_id));
  const selectedBarber = barbers.find((barber) => Number(barber.id) === Number(form.barber_id));
  const availableDates = useMemo(() => Array.from({ length: 21 }, (_, index) => localDateString(index + 1)), []);

  function updateForm(values) {
    setForm((current) => ({ ...current, ...values }));
  }

  function selectService(service) {
    if (!service.id) {
      setError('O agendamento está sendo preparado. Fale pelo WhatsApp para confirmar seu horário.');
      return;
    }
    setError('');
    updateForm({ service_id: service.id, appointment_date: '', start_time: '' });
    setStep(barberLocked ? 3 : 2);
  }

  function selectBarber(barberId) {
    setError('');
    updateForm({ barber_id: barberId, appointment_date: '', start_time: '' });
    setStep(3);
  }

  async function fetchSlots() {
    if (!form.service_id || !form.appointment_date) return;
    setBusy(true);
    setError('');
    setSlots([]);
    try {
      const params = query({
        service_id: form.service_id,
        appointment_date: form.appointment_date,
        barber_id: form.barber_id || undefined,
      });
      const data = await api('/availability' + params);
      setSlots(Array.isArray(data) ? data : []);
      setStep(4);
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function submitBooking() {
    setBusy(true);
    setError('');
    try {
      const data = await api('/appointments', { method: 'POST', body: form });
      setConfirmation(data);
      setStep(7);
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setBusy(false);
    }
  }

  function goBack() {
    if (step === 7) return close();
    if (step === 3 && barberLocked) return setStep(1);
    setStep(Math.max(1, step - 1));
  }

  const steps = ['Serviço', 'Profissional', 'Data', 'Horário', 'Dados', 'Confirmar'];
  const confirmationService = confirmation && confirmation.service ? confirmation.service : selectedService;
  const confirmationBarber = confirmation && confirmation.barber ? confirmation.barber : selectedBarber;
  const confirmationCode = confirmation && confirmation.public_token;
  const confirmationMessage = 'Olá! Meu horário foi agendado na Talaska Barber Shop.' +
    '\n\nCódigo: ' + (confirmationCode || '') +
    '\nProfissional: ' + ((confirmationBarber && confirmationBarber.name) || '') +
    '\nServiço: ' + ((confirmationService && confirmationService.name) || '') +
    '\nData: ' + formatDate(form.appointment_date) +
    '\nHorário: ' + form.start_time;

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="booking-title">
      <div className="booking-modal">
        <button className="modal-close" type="button" onClick={close} aria-label="Fechar agendamento"><X /></button>
        {step !== 7 ? (
          <button className="modal-back" type="button" onClick={goBack} aria-label="Voltar uma etapa"><ChevronLeft size={20} /> Voltar</button>
        ) : null}

        {confirmation ? (
          <div className="booking-success">
            <CheckCircle size={58} strokeWidth={1.35} />
            <p className="eyebrow">HORÁRIO SOLICITADO</p>
            <h2 id="booking-title">Seu horário está reservado.</h2>
            <p className="booking-success__lead">Guarde o código abaixo para consultar ou cancelar dentro do prazo.</p>
            <strong className="booking-code">{confirmationCode}</strong>
            <div className="booking-receipt">
              <span>Serviço <b>{confirmationService && confirmationService.name}</b></span>
              <span>Profissional <b>{confirmationBarber && confirmationBarber.name}</b></span>
              <span>Quando <b>{formatDate(form.appointment_date)} às {form.start_time}</b></span>
            </div>
            <a className="button button--gold" href={whatsappLink(settings.whatsapp, confirmationMessage)} target="_blank" rel="noreferrer">
              Enviar pelo WhatsApp <ExternalLink size={16} />
            </a>
            <button className="text-button text-button--center" type="button" onClick={close}>Concluído</button>
          </div>
        ) : (
          <>
            <p className="eyebrow">AGENDAMENTO ONLINE</p>
            <h2 id="booking-title">{selectedBarber && barberLocked ? 'Agendamento com ' + selectedBarber.name : 'Reserve seu horário'}</h2>
            <div className="booking-steps" aria-label={'Etapa ' + step + ' de 6'}>
              {steps.map((label, index) => (
                <span key={label} className={step === index + 1 ? 'is-active' : step > index + 1 ? 'is-complete' : ''}>
                  <i>{index + 1}</i>{label}
                </span>
              ))}
            </div>
            {error ? <Notice>{error}</Notice> : null}

            {step === 1 ? (
              <section className="booking-step">
                <h3>Qual serviço você procura?</h3>
                <div className="booking-choices booking-choices--services">
                  {services.map((service) => (
                    <button key={service.id || service.name} type="button" className="booking-choice" onClick={() => selectService(service)}>
                      <Scissors size={21} />
                      <b>{service.name}</b>
                      <small>{service.description || 'Atendimento personalizado.'}</small>
                      <em>{formatMoney(service.price)} {service.duration_minutes ? '· ' + service.duration_minutes + ' min' : ''}</em>
                    </button>
                  ))}
                </div>
              </section>
            ) : null}

            {step === 2 ? (
              <section className="booking-step">
                <h3>Com quem você quer agendar?</h3>
                <div className="booking-choices booking-choices--barbers">
                  <button type="button" className="booking-choice booking-choice--any" onClick={() => selectBarber(null)}>
                    <Users size={24} />
                    <b>Qualquer profissional</b>
                    <small>Mostraremos o melhor horário disponível.</small>
                  </button>
                  {barbers.map((barber) => (
                    <button key={barber.id || barber.name} type="button" className={'booking-choice booking-choice--barber' + (Number(form.barber_id) === Number(barber.id) ? ' is-selected' : '')} onClick={() => selectBarber(barber.id)}>
                      <BarberPortrait barber={barber} alt="" />
                      <b>{barber.name}</b>
                      <small>{barber.specialties || barber.bio || 'Talaska Barber Shop'}</small>
                    </button>
                  ))}
                </div>
              </section>
            ) : null}

            {step === 3 ? (
              <section className="booking-step">
                <div className="booking-step__title">
                  <div>
                    <h3>Em qual dia?</h3>
                    <p>{selectedBarber ? 'Você escolheu ' + selectedBarber.name + '.' : 'Escolha uma data para ver todos os horários.'}</p>
                  </div>
                  {barberLocked ? (
                    <button className="link-button" type="button" onClick={() => { setBarberLocked(false); setStep(2); }}>Trocar profissional</button>
                  ) : null}
                </div>
                <div className="date-picker">
                  {availableDates.map((date) => (
                    <button key={date} type="button" className={form.appointment_date === date ? 'is-selected' : ''} onClick={() => updateForm({ appointment_date: date, start_time: '' })}>
                      <span>{formatWeekdayShort(date)}</span>
                      <b>{date.slice(8)}</b>
                      <small>{formatMonthShort(date)}</small>
                    </button>
                  ))}
                </div>
                <Button className="button--gold" icon={ChevronRight} disabled={!form.appointment_date || busy} onClick={fetchSlots}>
                  {busy ? 'Buscando horários...' : 'Ver horários'}
                </Button>
              </section>
            ) : null}

            {step === 4 ? (
              <section className="booking-step">
                <h3>Escolha o melhor horário</h3>
                <p>{selectedService ? selectedService.name + ' · ' + (selectedService.duration_minutes || '—') + ' min' : ''}</p>
                <div className="slot-results">
                  {slots.filter((group) => group.slots && group.slots.length).map((group) => (
                    <article className="slot-group" key={group.barber && group.barber.id}>
                      <div>
                        <BarberPortrait barber={group.barber} alt="" />
                        <b>{group.barber && group.barber.name}</b>
                      </div>
                      <div className="slot-grid">
                        {group.slots.map((slot) => (
                          <button key={slot} type="button" onClick={() => { updateForm({ barber_id: group.barber.id, start_time: slot }); setStep(5); }}>
                            {slot}
                          </button>
                        ))}
                      </div>
                    </article>
                  ))}
                  {slots.length > 0 && !slots.some((group) => group.slots && group.slots.length) ? (
                    <div className="empty-state"><Clock size={28} /><p>Nenhum horário livre nesta data. Escolha outro dia.</p></div>
                  ) : null}
                </div>
              </section>
            ) : null}

            {step === 5 ? (
              <section className="booking-step booking-form">
                <h3>Quase lá. Como podemos falar com você?</h3>
                <label>Nome completo
                  <input autoComplete="name" value={form.customer_name} onChange={(event) => updateForm({ customer_name: event.target.value })} placeholder="Seu nome" />
                </label>
                <label>WhatsApp
                  <input autoComplete="tel" inputMode="tel" value={form.customer_phone} onChange={(event) => updateForm({ customer_phone: event.target.value })} placeholder="(51) 99999-9999" />
                </label>
                <label>E-mail <small>opcional</small>
                  <input autoComplete="email" type="email" value={form.customer_email} onChange={(event) => updateForm({ customer_email: event.target.value })} placeholder="voce@email.com" />
                </label>
                <label>Observação <small>opcional</small>
                  <textarea value={form.notes} onChange={(event) => updateForm({ notes: event.target.value })} placeholder="Alguma preferência para o atendimento?" rows="3" />
                </label>
                <Button className="button--gold" icon={ChevronRight} disabled={!form.customer_name.trim() || !form.customer_phone.trim()} onClick={() => setStep(6)}>
                  Revisar agendamento
                </Button>
              </section>
            ) : null}

            {step === 6 ? (
              <section className="booking-step">
                <h3>Confira seus dados</h3>
                <div className="booking-summary">
                  <span><small>Serviço</small><b>{selectedService && selectedService.name}</b></span>
                  <span><small>Profissional</small><b>{selectedBarber && selectedBarber.name}</b></span>
                  <span><small>Data e horário</small><b>{formatDate(form.appointment_date)} às {form.start_time}</b></span>
                  <span><small>Valor</small><b>{selectedService ? formatMoney(selectedService.price) : '—'}</b></span>
                </div>
                <Button className="button--gold" icon={ShieldCheck} disabled={busy} onClick={submitBooking}>
                  {busy ? 'Confirmando...' : 'Confirmar agendamento'}
                </Button>
              </section>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

function GallerySection({ items }) {
  const [selected, setSelected] = useState(null);
  return (
    <section id="galeria" className="public-section gallery-section">
      <p className="eyebrow">— NOSSO TRABALHO —</p>
      <h2>Detalhes que fazem a diferença</h2>
      {items.length ? (
        <div className="gallery-grid">
          {items.map((item) => (
            <button key={item.id} className="gallery-card" type="button" onClick={() => setSelected(item)} aria-label={'Ampliar ' + (item.title || 'foto da galeria')}>
              <img src={item.image_url} alt={item.alt_text || item.title || 'Trabalho da Talaska Barber Shop'} loading="lazy" />
              {item.title ? <span>{item.title}</span> : null}
            </button>
          ))}
        </div>
      ) : (
        <div className="gallery-empty"><ImageIcon size={31} /><p>As fotos reais dos trabalhos serão adicionadas em breve.</p></div>
      )}
      {selected ? (
        <div className="lightbox" role="dialog" aria-modal="true" aria-label={selected.title || 'Imagem ampliada'} onClick={() => setSelected(null)}>
          <button type="button" className="modal-close" onClick={() => setSelected(null)} aria-label="Fechar imagem"><X /></button>
          <img src={selected.image_url} alt={selected.alt_text || selected.title || 'Trabalho da Talaska Barber Shop'} onClick={(event) => event.stopPropagation()} />
        </div>
      ) : null}
    </section>
  );
}

function Home() {
  const [services, setServices] = useState(fallbackServices);
  const [barbers, setBarbers] = useState(fallbackBarbers);
  const [gallery, setGallery] = useState([]);
  const [settings, setSettings] = useState({});
  const [apiNotice, setApiNotice] = useState('');
  const [booking, setBooking] = useState(null);

  useEffect(() => {
    let active = true;
    async function loadPublicData() {
      const results = await Promise.allSettled([
        api('/services'),
        api('/barbers'),
        api('/settings'),
        api('/gallery'),
      ]);
      if (!active) return;
      const [serviceResult, barberResult, settingsResult, galleryResult] = results;
      if (serviceResult.status === 'fulfilled' && Array.isArray(serviceResult.value) && serviceResult.value.length) {
        setServices(serviceResult.value);
      }
      if (barberResult.status === 'fulfilled' && Array.isArray(barberResult.value) && barberResult.value.length) {
        setBarbers(barberResult.value);
      }
      if (settingsResult.status === 'fulfilled' && settingsResult.value) setSettings(settingsResult.value);
      if (galleryResult.status === 'fulfilled' && Array.isArray(galleryResult.value)) setGallery(galleryResult.value);
      if (serviceResult.status === 'rejected' || barberResult.status === 'rejected') {
        setApiNotice('O agendamento online está indisponível no momento. Você ainda pode chamar a Talaska pelo WhatsApp.');
      }
    }
    loadPublicData();
    return () => { active = false; };
  }, []);

  function openBooking(barberId = null, serviceId = null) {
    setBooking({ barberId, serviceId, key: String(Date.now()) });
  }

  const whatsapp = settings.whatsapp || DEFAULT_WHATSAPP;
  const heroMessage = 'Olá! Gostaria de agendar um horário na Talaska Barber Shop.';

  return (
    <>
      <PublicHeader onBook={openBooking} instagram={settings.instagram} />
      <main>
        <section id="inicio" className="hero" style={{ '--hero-desktop-position': settings.hero_desktop_position || '72% center', '--hero-mobile-position': settings.hero_mobile_position || '64% center' }}>
          <div className="hero-copy">
            <p className="eyebrow">— MAIS QUE UM CORTE —</p>
            <h1>TRANSFORME<br />SEU ESTILO</h1>
            <p className="hero-copy__description">Cortes premium, barba impecável e atendimento que faz a diferença.</p>
            <div className="hero-actions">
              <Button className="button--gold" icon={Calendar} onClick={openBooking}>Agende seu horário</Button>
              <a className="hero-whatsapp" href={whatsappLink(whatsapp, heroMessage)} target="_blank" rel="noopener noreferrer">Fale pelo WhatsApp <ArrowRight size={14} /></a>
            </div>
          </div>
          <picture className="hero-photo">
            <source media="(max-width: 680px)" srcSet={heroMobile} />
            <img src={heroDesktop} alt="Atendimento Talaska Barber Shop" fetchPriority="high" />
          </picture>
        </section>

        {apiNotice ? <div className="site-notice"><Notice>{apiNotice}</Notice></div> : null}

        <section id="servicos" className="public-section services-section">
          <p className="eyebrow">— NOSSOS SERVIÇOS —</p>
          <h2>Estilo, precisão e confiança</h2>
          <div className="service-grid">
            {services.map((service) => <ServiceCard key={service.id || service.name} service={service} onBook={openBooking} />)}
          </div>
        </section>

        <section id="equipe" className="public-section team-section">
          <p className="eyebrow">— NOSSA EQUIPE —</p>
          <h2>Profissionais que entendem de estilo</h2>
          <p className="section-intro">Escolha quem vai cuidar do seu visual. Ao clicar, ele já fica selecionado no seu agendamento.</p>
          <div className="barber-grid">
            {barbers.map((barber) => <BarberCard key={barber.id || barber.name} barber={barber} onBook={openBooking} />)}
          </div>
        </section>

        <GallerySection items={gallery} />

        <section className="about-section">
          <div>
            <p className="eyebrow">— SOBRE A TALASKA —</p>
            <h2>Mais do que um corte, uma experiência.</h2>
            <p>{settings.about || 'A Talaska Barber Shop é um espaço criado para quem valoriza estilo, cuidado e atendimento de qualidade.'}</p>
          </div>
          <div className="about-actions">
            <MapPin size={34} />
            <strong>{settings.address || 'Avenida Santa Rita, 627 · Centro'}</strong>
            <a href={'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(settings.address || 'Avenida Santa Rita, 627')} target="_blank" rel="noopener noreferrer">
              Como chegar <ExternalLink size={15} />
            </a>
            {settings.instagram ? <a className="instagram-follow" href={settings.instagram} target="_blank" rel="noopener noreferrer"><Instagram size={17} /> Siga a Talaska no Instagram</a> : null}
          </div>
        </section>
      </main>
      <Footer settings={settings} />
      <a className="whatsapp-float" href={whatsappLink(whatsapp, heroMessage)} target="_blank" rel="noopener noreferrer" aria-label="Falar com a Talaska pelo WhatsApp">
        <Phone size={22} />
      </a>
      {booking ? (
        <BookingModal
          key={booking.key}
          close={() => setBooking(null)}
          services={services}
          barbers={barbers}
          presetBarberId={booking.barberId}
          presetServiceId={booking.serviceId}
          settings={settings}
        />
      ) : null}
    </>
  );
}

function AdminLogin({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const response = await api('/auth/login', { method: 'POST', body: { email, password } });
      if (!response || !response.access_token) throw new Error('A API não retornou uma sessão válida.');
      localStorage.setItem(TOKEN_KEY, response.access_token);
      onLogin(response.access_token);
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="admin-login">
      <a className="admin-login__back" href="/">← Voltar ao site</a>
      <Brand />
      <form className="admin-login__form" onSubmit={submit}>
        <p className="eyebrow">ÁREA RESTRITA</p>
        <h1>Gestão Talaska</h1>
        <p>Entre com sua conta administrativa para controlar agenda, equipe, serviços e disponibilidade.</p>
        {error ? <Notice>{error}</Notice> : null}
        <label>E-mail
          <input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="voce@talaska.com" required />
        </label>
        <label>Senha
          <input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Sua senha" required />
        </label>
        <Button type="submit" className="button--gold" icon={Lock} disabled={busy}>{busy ? 'Entrando...' : 'Entrar no painel'}</Button>
      </form>
    </main>
  );
}

function Metric({ label, value, money = false }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{money ? formatMoney(value) : (value === undefined || value === null ? '—' : value)}</strong>
    </article>
  );
}

function AdminDashboard({ request }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(await request('/admin/dashboard'));
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => { load(); }, [load]);

  return (
    <section className="admin-view">
      <div className="admin-view__heading">
        <div><p className="eyebrow">GESTÃO TALASKA</p><h1>Visão geral</h1></div>
        <Button className="button--light" icon={RefreshCw} onClick={load} disabled={loading}>Atualizar</Button>
      </div>
      {error ? <Notice>{error}</Notice> : null}
      <div className="metric-grid">
        <Metric label="Agendamentos hoje" value={data && data.appointments_today} />
        <Metric label="Agendamentos amanhã" value={data && data.appointments_tomorrow} />
        <Metric label="Agendamentos na semana" value={data && data.appointments_week} />
        <Metric label="Clientes cadastrados" value={data && data.customers} />
        <Metric label="Faturamento hoje" value={data && data.revenue_today} money />
        <Metric label="Faturamento da semana" value={data && data.revenue_week} money />
        <Metric label="Faturamento do mês" value={data && data.revenue_month} money />
        <Metric label="Ticket médio" value={data && data.ticket_average} money />
        <Metric label="Concluídos" value={data && data.completed} />
        <Metric label="Cancelamentos" value={data && data.cancellations} />
        <Metric label="Não compareceram" value={data && data.no_shows} />
      </div>
      {!loading && data ? (
        <div className="dashboard-details">
          <article className="data-card"><h2>Serviços mais agendados</h2>{data.top_services?.length ? data.top_services.map((item) => <p className="ranking-row" key={item.name}><span>{item.name}</span><b>{item.appointments}</b></p>) : <p className="muted-copy">Ainda não há atendimentos concluídos no período.</p>}</article>
          <article className="data-card"><h2>Desempenho e comissão</h2>{data.barber_performance?.length ? data.barber_performance.map((item) => <p className="ranking-row ranking-row--barber" key={item.barber_id}><span><b>{item.name}</b><small>{item.appointments} concluído(s) · {formatMoney(item.revenue)}</small></span><b>{formatMoney(item.estimated_commission)}</b></p>) : <p className="muted-copy">A comissão será calculada quando houver atendimentos concluídos.</p>}</article>
        </div>
      ) : null}
      {!loading && data ? <p className="admin-caption">Os indicadores consideram os dados registrados na agenda.</p> : null}
    </section>
  );
}

function AdminAppointments({ request }) {
  const [appointments, setAppointments] = useState([]);
  const [start, setStart] = useState(localDateString(0));
  const [end, setEnd] = useState(localDateString(14));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [savingId, setSavingId] = useState(null);
  const [status, setStatus] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await request('/admin/appointments' + query({ start, end, status }));
      setAppointments(Array.isArray(data) ? data : []);
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setLoading(false);
    }
  }, [request, start, end, status]);

  async function exportCsv() {
    try {
      const blob = await request('/admin/appointments/export' + query({ start, end }), { responseType: 'blob' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'agenda-talaska.csv';
      link.click();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(humanError(requestError));
    }
  }

  useEffect(() => { load(); }, [load]);

  async function updateStatus(appointment, status) {
    setSavingId(appointment.id);
    setError('');
    try {
      const updated = await request('/admin/appointments/' + appointment.id, { method: 'PUT', body: { status } });
      setAppointments((current) => current.map((item) => item.id === appointment.id ? updated : item));
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setSavingId(null);
    }
  }

  return (
    <section className="admin-view">
      <div className="admin-view__heading">
        <div><p className="eyebrow">AGENDA</p><h1>Agendamentos</h1></div>
        <div className="heading-actions"><Button className="button--light" icon={Download} onClick={exportCsv}>Exportar CSV</Button><Button className="button--light" icon={RefreshCw} onClick={load} disabled={loading}>Atualizar</Button></div>
      </div>
      <div className="filter-row">
        <label>De <input type="date" value={start} onChange={(event) => setStart(event.target.value)} /></label>
        <label>Até <input type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></label>
        <label>Status <select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Todos</option>{Object.entries(APPOINTMENT_STATUSES).filter(([value]) => value !== 'pending').map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}</select></label>
      </div>
      {error ? <Notice>{error}</Notice> : null}
      <div className="data-card table-scroll">
        <table className="data-table">
          <thead><tr><th>Quando</th><th>Cliente</th><th>Serviço</th><th>Profissional</th><th>Status</th></tr></thead>
          <tbody>
            {appointments.map((appointment) => (
              <tr key={appointment.id}>
                <td><b>{formatDateTime(appointment.start_datetime)}</b><small>{formatMoney(appointment.price)}</small></td>
                <td>{appointment.customer && appointment.customer.name}<small>{appointment.customer && appointment.customer.phone}</small></td>
                <td>{appointment.service && appointment.service.name}</td>
                <td>{appointment.barber && appointment.barber.name}</td>
                <td>
                  <select className={'appointment-status appointment-status--' + appointmentStatus(appointment.status).tone} value={appointment.status === 'pending' ? 'scheduled' : appointment.status || 'scheduled'} disabled={savingId === appointment.id} onChange={(event) => updateStatus(appointment, event.target.value)}>
                    <option value="scheduled">Agendado</option>
                    <option value="confirmed">Confirmado</option>
                    <option value="completed">Concluído</option>
                    <option value="cancelled">Cancelado</option>
                    <option value="no_show">Não compareceu</option>
                  </select>
                </td>
              </tr>
            ))}
            {!loading && !appointments.length ? <tr><td colSpan="5" className="table-empty">Nenhum agendamento no período escolhido.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AdminCustomers({ request }) {
  const [term, setTerm] = useState('');
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const search = useCallback(async (value = term) => {
    setLoading(true);
    setError('');
    try {
      const data = await request('/admin/customers' + query({ q: value }));
      setCustomers(Array.isArray(data) ? data : []);
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setLoading(false);
    }
  }, [request, term]);

  useEffect(() => { search(''); }, []);

  return (
    <section className="admin-view">
      <div className="admin-view__heading"><div><p className="eyebrow">RELACIONAMENTO</p><h1>Clientes</h1></div></div>
      <form className="search-form" onSubmit={(event) => { event.preventDefault(); search(); }}>
        <Search size={19} />
        <input value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Buscar por nome ou WhatsApp" />
        <Button type="submit" className="button--dark">Buscar</Button>
      </form>
      {error ? <Notice>{error}</Notice> : null}
      <div className="data-card table-scroll">
        <table className="data-table">
          <thead><tr><th>Cliente</th><th>WhatsApp</th><th>E-mail</th><th>Visitas</th><th>Total gasto</th></tr></thead>
          <tbody>
            {customers.map((customer) => (
              <tr key={customer.id}>
                <td><b>{customer.name}</b></td>
                <td>{customer.phone}</td>
                <td>{customer.email || '—'}</td>
                <td>{customer.visits || 0}</td>
                <td>{formatMoney(customer.total_spent)}</td>
              </tr>
            ))}
            {!loading && !customers.length ? <tr><td colSpan="5" className="table-empty">Nenhum cliente encontrado.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function emptyBarber() {
  return { name: '', bio: '', specialties: '', photo_url: '', commission_percentage: '', display_order: '', active: true };
}

function emptyService() {
  return { name: '', description: '', price: '', price_on_request: false, duration_minutes: '45', image_url: '', display_order: '', active: true };
}

function EntityManager({ request, kind }) {
  const isBarber = kind === 'barbers';
  const title = isBarber ? 'Barbeiros' : 'Serviços e valores';
  const blank = isBarber ? emptyBarber : emptyService;
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(blank);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await request('/admin/' + kind);
      setItems(Array.isArray(data) ? data : []);
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setLoading(false);
    }
  }, [request, kind]);

  useEffect(() => { load(); }, [load]);

  function update(values) {
    setForm((current) => ({ ...current, ...values }));
  }

  function reset() {
    setForm(blank());
    setEditingId(null);
    setSuccess('');
  }

  function edit(item) {
    setEditingId(item.id);
    setSuccess('');
    setForm({
      ...blank(),
      ...item,
      commission_percentage: item.commission_percentage === null || item.commission_percentage === undefined ? '' : String(item.commission_percentage),
      price: item.price === null || item.price === undefined ? '' : String(item.price),
      duration_minutes: item.duration_minutes === null || item.duration_minutes === undefined ? '' : String(item.duration_minutes),
      display_order: item.display_order === null || item.display_order === undefined ? '' : String(item.display_order),
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function payload() {
    const result = { ...form };
    if (isBarber) {
      result.commission_percentage = form.commission_percentage === '' ? undefined : Number(form.commission_percentage);
      result.display_order = form.display_order === '' ? undefined : Number(form.display_order);
    } else {
      result.price = form.price === '' ? undefined : Number(form.price);
      result.duration_minutes = form.duration_minutes === '' ? undefined : Number(form.duration_minutes);
      result.display_order = form.display_order === '' ? undefined : Number(form.display_order);
    }
    return result;
  }

  async function submit(event) {
    event.preventDefault();
    const effectivePrice = Number(form.price || 0);
    if (!isBarber && form.active && effectivePrice <= 0 && !form.price_on_request) {
      setError('Informe um valor ou marque “Valor sob consulta” para publicar este serviço.');
      return;
    }
    if (!isBarber && form.active && effectivePrice <= 0 && form.price_on_request && !window.confirm('Confirmar publicação como “Valor sob consulta”? O site não exibirá R$ 0,00.')) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const result = await request('/admin/' + kind + (editingId ? '/' + editingId : ''), {
        method: editingId ? 'PUT' : 'POST',
        body: payload(),
      });
      setItems((current) => editingId
        ? current.map((item) => item.id === editingId ? result : item)
        : [...current, result]);
      reset();
      setSuccess(editingId ? 'Alterações salvas com sucesso.' : 'Novo registro cadastrado com sucesso.');
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(item) {
    setError('');
    try {
      const result = await request('/admin/' + kind + '/' + item.id, { method: 'PUT', body: { ...item, active: !item.active } });
      setItems((current) => current.map((entry) => entry.id === item.id ? result : entry));
    } catch (requestError) {
      setError(humanError(requestError));
    }
  }

  return (
    <section className="admin-view">
      <div className="admin-view__heading">
        <div><p className="eyebrow">{isBarber ? 'EQUIPE' : 'CATÁLOGO'}</p><h1>{title}</h1></div>
        <Button className="button--light" icon={RefreshCw} onClick={load} disabled={loading}>Atualizar</Button>
      </div>
      <div className="admin-two-columns">
        <form className="data-card editor-form" onSubmit={submit}>
          <div className="editor-form__heading">
            <h2>{editingId ? 'Editar registro' : isBarber ? 'Adicionar barbeiro' : 'Adicionar serviço'}</h2>
            {editingId ? <button type="button" className="link-button" onClick={reset}>Cancelar edição</button> : null}
          </div>
          {error ? <Notice>{error}</Notice> : null}
          {success ? <Notice tone="success">{success}</Notice> : null}
          <label>Nome
            <input value={form.name} onChange={(event) => update({ name: event.target.value })} placeholder={isBarber ? 'Nome do barbeiro' : 'Nome do serviço'} required />
          </label>
          {isBarber ? (
            <>
              <label>Especialidades
                <input value={form.specialties || ''} onChange={(event) => update({ specialties: event.target.value })} placeholder="Ex.: fade, navalhado, barba" />
              </label>
              <label>Biografia curta
                <textarea rows="3" value={form.bio || ''} onChange={(event) => update({ bio: event.target.value })} placeholder="Como este profissional atende?" />
              </label>
              <label>URL da foto
                <input type="url" value={form.photo_url || ''} onChange={(event) => update({ photo_url: event.target.value })} placeholder="https://..." />
              </label>
              <label>Comissão (%)
                <input type="number" min="0" max="100" step="0.01" value={form.commission_percentage || ''} onChange={(event) => update({ commission_percentage: event.target.value })} placeholder="0" />
              </label>
              <label>Ordem de exibição
                <input type="number" min="0" value={form.display_order || ''} onChange={(event) => update({ display_order: event.target.value })} placeholder="1" />
              </label>
            </>
          ) : (
            <>
              <label>Descrição
                <textarea rows="3" value={form.description || ''} onChange={(event) => update({ description: event.target.value })} placeholder="Explique o que está incluso." />
              </label>
              <div className="form-pair">
                <label>Valor (R$)
                  <input type="number" min="0" step="0.01" value={form.price || ''} onChange={(event) => update({ price: event.target.value })} placeholder="0,00" />
                </label>
                <label>Duração (min)
                  <input type="number" min="5" max="480" step="5" value={form.duration_minutes || ''} onChange={(event) => update({ duration_minutes: event.target.value })} />
                </label>
              </div>
              <label className="toggle-row toggle-row--consultation">
                <input type="checkbox" checked={Boolean(form.price_on_request)} onChange={(event) => update({ price_on_request: event.target.checked })} />
                <span><b>Valor sob consulta</b><small>Use somente quando o serviço não tiver preço definido. O site nunca mostrará R$ 0,00.</small></span>
              </label>
              <label>URL da imagem <small>opcional</small>
                <input type="url" value={form.image_url || ''} onChange={(event) => update({ image_url: event.target.value })} placeholder="https://..." />
              </label>
              <label>Ordem de exibição
                <input type="number" min="0" value={form.display_order || ''} onChange={(event) => update({ display_order: event.target.value })} placeholder="1" />
              </label>
            </>
          )}
          <label className="toggle-row">
            <input type="checkbox" checked={Boolean(form.active)} onChange={(event) => update({ active: event.target.checked })} />
            <span><b>Registro ativo</b><small>{isBarber ? 'Aparece na equipe e pode receber agendamentos.' : 'Aparece na página e pode ser agendado.'}</small></span>
          </label>
          <Button type="submit" className="button--gold" icon={Save} disabled={saving}>{saving ? 'Salvando...' : editingId ? 'Salvar alterações' : 'Cadastrar'}</Button>
        </form>
        <div className="data-card entity-list">
          <h2>{isBarber ? 'Equipe cadastrada' : 'Serviços cadastrados'}</h2>
          {items.map((item) => (
            <article className="entity-row" key={item.id}>
              {isBarber ? <BarberPortrait barber={item} alt="" /> : <div className="entity-row__icon"><Scissors size={19} /></div>}
              <div>
                <b>{item.name}</b>
                <small>{isBarber ? (item.specialties || item.bio || 'Sem especialidade informada') : formatMoney(item.price) + ' · ' + item.duration_minutes + ' min'}</small>
              </div>
              <span className={'status-dot ' + (item.active ? 'status-dot--active' : 'status-dot--inactive')}>{item.active ? 'Ativo' : 'Inativo'}</span>
              <div className="entity-row__actions">
                <button type="button" onClick={() => edit(item)} aria-label={'Editar ' + item.name}><Pencil size={16} /></button>
                <button type="button" onClick={() => toggleActive(item)} aria-label={(item.active ? 'Desativar ' : 'Ativar ') + item.name}>{item.active ? <Ban size={16} /> : <CheckCircle size={16} />}</button>
              </div>
            </article>
          ))}
          {!loading && !items.length ? <div className="empty-state"><UserCog size={27} /><p>Nenhum registro cadastrado ainda.</p></div> : null}
        </div>
      </div>
    </section>
  );
}

function AdminSettings({ request }) {
  const [form, setForm] = useState({ instagram: '', whatsapp: '', address: '', about: '', hero_desktop_position: '', hero_mobile_position: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    request('/admin/settings').then((data) => setForm((current) => ({ ...current, ...data }))).catch((requestError) => setError(humanError(requestError)));
  }, [request]);

  async function submit(event) {
    event.preventDefault(); setSaving(true); setError(''); setSuccess('');
    try { setForm(await request('/admin/settings', { method: 'PUT', body: form })); setSuccess('Configurações salvas. O site público atualizará em alguns minutos.'); }
    catch (requestError) { setError(humanError(requestError)); }
    finally { setSaving(false); }
  }

  return <section className="admin-view"><div className="admin-view__heading"><div><p className="eyebrow">SITE PÚBLICO</p><h1>Configurações</h1></div></div><form className="data-card editor-form admin-settings" onSubmit={submit}>
    {error ? <Notice>{error}</Notice> : null}{success ? <Notice tone="success">{success}</Notice> : null}
    <label>Instagram oficial<input type="url" value={form.instagram || ''} onChange={(event) => setForm((current) => ({ ...current, instagram: event.target.value }))} placeholder="https://www.instagram.com/..." /></label>
    <label>WhatsApp<input value={form.whatsapp || ''} onChange={(event) => setForm((current) => ({ ...current, whatsapp: event.target.value }))} placeholder="Somente números com DDD" /></label>
    <label>Endereço<input value={form.address || ''} onChange={(event) => setForm((current) => ({ ...current, address: event.target.value }))} /></label>
    <label>Texto sobre a barbearia<textarea rows="4" value={form.about || ''} onChange={(event) => setForm((current) => ({ ...current, about: event.target.value }))} /></label>
    <div className="form-pair"><label>Posição imagem desktop<input value={form.hero_desktop_position || ''} onChange={(event) => setForm((current) => ({ ...current, hero_desktop_position: event.target.value }))} placeholder="Ex.: 72% center" /></label><label>Posição imagem celular<input value={form.hero_mobile_position || ''} onChange={(event) => setForm((current) => ({ ...current, hero_mobile_position: event.target.value }))} placeholder="Ex.: 64% center" /></label></div>
    <p className="muted-copy">Use valores CSS de posição, como “72% center”, apenas se precisar ajustar o enquadramento sem trocar a foto.</p>
    <Button type="submit" className="button--gold" icon={Save} disabled={saving}>{saving ? 'Salvando...' : 'Salvar configurações'}</Button>
  </form></section>;
}

function AdminGallery({ request }) {
  const blank = () => ({ image_url: '', title: '', alt_text: '', category: '', display_order: '', active: true });
  const [items, setItems] = useState([]); const [form, setForm] = useState(blank); const [editingId, setEditingId] = useState(null); const [error, setError] = useState(''); const [saving, setSaving] = useState(false);
  const load = useCallback(async () => { try { const data = await request('/admin/gallery'); setItems(Array.isArray(data) ? data : []); } catch (requestError) { setError(humanError(requestError)); } }, [request]);
  useEffect(() => { load(); }, [load]);
  function update(values) { setForm((current) => ({ ...current, ...values })); }
  async function submit(event) { event.preventDefault(); setSaving(true); setError(''); try { const body = { ...form, display_order: form.display_order === '' ? 0 : Number(form.display_order) }; const result = await request('/admin/gallery' + (editingId ? '/' + editingId : ''), { method: editingId ? 'PUT' : 'POST', body }); setItems((current) => editingId ? current.map((item) => item.id === editingId ? result : item) : [...current, result]); setForm(blank()); setEditingId(null); } catch (requestError) { setError(humanError(requestError)); } finally { setSaving(false); } }
  async function remove(item) { if (!window.confirm('Remover esta imagem da galeria?')) return; try { await request('/admin/gallery/' + item.id, { method: 'DELETE' }); setItems((current) => current.filter((entry) => entry.id !== item.id)); } catch (requestError) { setError(humanError(requestError)); } }
  return <section className="admin-view"><div className="admin-view__heading"><div><p className="eyebrow">SITE PÚBLICO</p><h1>Galeria de trabalhos</h1></div><Button className="button--light" icon={RefreshCw} onClick={load}>Atualizar</Button></div><div className="admin-two-columns"><form className="data-card editor-form" onSubmit={submit}><h2>{editingId ? 'Editar imagem' : 'Adicionar foto real'}</h2>{error ? <Notice>{error}</Notice> : null}<label>URL da imagem<input type="url" value={form.image_url} onChange={(event) => update({ image_url: event.target.value })} placeholder="https://..." required /></label><label>Título <small>opcional</small><input value={form.title || ''} onChange={(event) => update({ title: event.target.value })} /></label><label>Texto alternativo<input value={form.alt_text || ''} onChange={(event) => update({ alt_text: event.target.value })} placeholder="Descreva a foto para acessibilidade" /></label><div className="form-pair"><label>Categoria <input value={form.category || ''} onChange={(event) => update({ category: event.target.value })} /></label><label>Ordem<input type="number" min="0" value={form.display_order || ''} onChange={(event) => update({ display_order: event.target.value })} /></label></div><label className="toggle-row"><input type="checkbox" checked={Boolean(form.active)} onChange={(event) => update({ active: event.target.checked })} /><span><b>Publicar imagem</b><small>Aparece no site quando estiver ativa.</small></span></label><Button className="button--gold" type="submit" icon={Save} disabled={saving}>{saving ? 'Salvando...' : editingId ? 'Salvar imagem' : 'Adicionar à galeria'}</Button></form><div className="data-card gallery-admin-list"><h2>Imagens cadastradas</h2>{items.map((item) => <article className="gallery-admin-row" key={item.id}><img src={item.image_url} alt="" loading="lazy" /><div><b>{item.title || 'Sem título'}</b><small>{item.active ? 'Ativa' : 'Inativa'} · Ordem {item.display_order || 0}</small></div><div className="entity-row__actions"><button type="button" onClick={() => { setForm({ ...item, display_order: String(item.display_order || '') }); setEditingId(item.id); }} aria-label="Editar imagem"><Pencil size={16} /></button><button type="button" onClick={() => remove(item)} aria-label="Remover imagem"><Trash2 size={16} /></button></div></article>)}{!items.length ? <div className="empty-state"><ImageIcon size={27} /><p>Sem fotos cadastradas. Adicione apenas fotos reais autorizadas.</p></div> : null}</div></div></section>;
}

function AdminHours({ request }) {
  const [businessHours, setBusinessHours] = useState([]);
  const [barberHours, setBarberHours] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [scope, setScope] = useState('business');
  const [form, setForm] = useState({ weekday: '0', start_time: '09:00', end_time: '18:00', barber_id: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const results = await Promise.allSettled([
      request('/admin/business-hours'),
      request('/admin/barber-hours'),
      request('/admin/barbers'),
    ]);
    const [businessResult, barberResult, peopleResult] = results;
    if (businessResult.status === 'fulfilled') setBusinessHours(Array.isArray(businessResult.value) ? businessResult.value : []);
    if (barberResult.status === 'fulfilled') setBarberHours(Array.isArray(barberResult.value) ? barberResult.value : []);
    if (peopleResult.status === 'fulfilled') setBarbers(Array.isArray(peopleResult.value) ? peopleResult.value.filter((barber) => barber.active) : []);
    const firstError = results.find((result) => result.status === 'rejected');
    if (firstError) setError('A área de disponibilidade precisa estar ativa na API para carregar e salvar horários.');
    setLoading(false);
  }, [request]);

  useEffect(() => { load(); }, [load]);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const body = {
        weekday: Number(form.weekday),
        start_time: form.start_time,
        end_time: form.end_time,
        active: true,
      };
      if (scope === 'barber') body.barber_id = Number(form.barber_id);
      const response = await request('/admin/' + (scope === 'business' ? 'business-hours' : 'barber-hours'), { method: 'POST', body });
      if (scope === 'business') setBusinessHours((current) => [...current, response]);
      else setBarberHours((current) => [...current, response]);
      setSuccess('Horário disponibilizado com sucesso.');
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setSaving(false);
    }
  }

  async function removeHour(hour, resource) {
    if (!window.confirm('Remover este horário disponível?')) return;
    setError('');
    try {
      await request('/admin/' + resource + '/' + hour.id, { method: 'DELETE' });
      if (resource === 'business-hours') setBusinessHours((current) => current.filter((entry) => entry.id !== hour.id));
      else setBarberHours((current) => current.filter((entry) => entry.id !== hour.id));
    } catch (requestError) {
      setError(humanError(requestError));
    }
  }

  async function useBusinessHours(barber) {
    if (!window.confirm('Remover os horários personalizados de ' + barber.name + ' e voltar a usar o horário geral?')) return;
    setError('');
    setSuccess('');
    try {
      await request('/admin/barber-hours/' + barber.id + '/use-business-hours', { method: 'POST' });
      setBarberHours((current) => current.filter((hour) => Number(hour.barber_id) !== Number(barber.id)));
      setSuccess(barber.name + ' voltou a usar o horário geral da barbearia.');
    } catch (requestError) {
      setError(humanError(requestError));
    }
  }

  function HourList({ title, hours, resource, showBarber }) {
    return (
      <div className="data-card hours-list">
        <h2>{title}</h2>
        {hours.map((hour) => {
          const barber = barbers.find((person) => Number(person.id) === Number(hour.barber_id));
          return (
            <div className="hour-row" key={hour.id}>
              <Clock size={17} />
              <span><b>{weekdayLabel(hour.weekday)}</b><small>{showBarber && barber ? barber.name + ' · ' : ''}{hour.start_time}–{hour.end_time}</small></span>
              <span className={'status-dot ' + (hour.active ? 'status-dot--active' : 'status-dot--inactive')}>{hour.active ? 'Ativo' : 'Inativo'}</span>
              <button type="button" aria-label="Remover horário" onClick={() => removeHour(hour, resource)}><Trash2 size={16} /></button>
            </div>
          );
        })}
        {!loading && !hours.length ? <p className="muted-copy">Nenhum horário definido.</p> : null}
      </div>
    );
  }

  return (
    <section className="admin-view">
      <div className="admin-view__heading">
        <div><p className="eyebrow">DISPONIBILIDADE</p><h1>Horários de atendimento</h1></div>
        <Button className="button--light" icon={RefreshCw} onClick={load} disabled={loading}>Atualizar</Button>
      </div>
      <div className="admin-two-columns">
        <form className="data-card editor-form" onSubmit={submit}>
          <h2>Adicionar disponibilidade</h2>
          {error ? <Notice>{error}</Notice> : null}
          {success ? <Notice tone="success">{success}</Notice> : null}
          <label>Aplicar para
            <select value={scope} onChange={(event) => setScope(event.target.value)}>
              <option value="business">Toda a barbearia</option>
              <option value="barber">Um barbeiro específico</option>
            </select>
          </label>
          {scope === 'barber' ? (
            <label>Barbeiro
              <select value={form.barber_id} onChange={(event) => setForm((current) => ({ ...current, barber_id: event.target.value }))} required>
                <option value="">Selecione</option>
                {barbers.map((barber) => <option key={barber.id} value={barber.id}>{barber.name}</option>)}
              </select>
            </label>
          ) : null}
          <label>Dia da semana
            <select value={form.weekday} onChange={(event) => setForm((current) => ({ ...current, weekday: event.target.value }))}>
              {WEEKDAYS.map((weekday) => <option key={weekday.value} value={weekday.value}>{weekday.label}</option>)}
            </select>
          </label>
          <div className="form-pair">
            <label>Abre
              <input type="time" value={form.start_time} onChange={(event) => setForm((current) => ({ ...current, start_time: event.target.value }))} required />
            </label>
            <label>Fecha
              <input type="time" value={form.end_time} onChange={(event) => setForm((current) => ({ ...current, end_time: event.target.value }))} required />
            </label>
          </div>
          <Button type="submit" className="button--gold" icon={Plus} disabled={saving || (scope === 'barber' && !form.barber_id)}>{saving ? 'Salvando...' : 'Adicionar horário'}</Button>
        </form>
        <div className="hours-stack">
          <HourList title="Horário geral" hours={businessHours} resource="business-hours" />
          <div className="hours-custom">
            <HourList title="Horários por barbeiro" hours={barberHours} resource="barber-hours" showBarber />
            {barbers.filter((barber) => barberHours.some((hour) => Number(hour.barber_id) === Number(barber.id))).map((barber) => (
              <button className="hour-reset" type="button" key={barber.id} onClick={() => useBusinessHours(barber)}>
                {barber.name}: usar horário geral
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function AdminBlocks({ request }) {
  const [blocks, setBlocks] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [form, setForm] = useState({ barber_id: '', start_datetime: '', end_datetime: '', reason: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const results = await Promise.allSettled([request('/admin/blocked-times'), request('/admin/barbers')]);
    if (results[0].status === 'fulfilled') setBlocks(Array.isArray(results[0].value) ? results[0].value : []);
    if (results[1].status === 'fulfilled') setBarbers(Array.isArray(results[1].value) ? results[1].value : []);
    if (results.some((result) => result.status === 'rejected')) setError('A área de bloqueios precisa estar ativa na API para carregar e salvar indisponibilidades.');
    setLoading(false);
  }, [request]);

  useEffect(() => { load(); }, [load]);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const response = await request('/admin/blocked-times', {
        method: 'POST',
        body: {
          barber_id: form.barber_id ? Number(form.barber_id) : null,
          start_datetime: form.start_datetime,
          end_datetime: form.end_datetime,
          reason: form.reason || null,
        },
      });
      setBlocks((current) => [...current, response]);
      setForm({ barber_id: '', start_datetime: '', end_datetime: '', reason: '' });
      setSuccess('Período bloqueado com sucesso.');
    } catch (requestError) {
      setError(humanError(requestError));
    } finally {
      setSaving(false);
    }
  }

  async function remove(block) {
    if (!window.confirm('Remover este bloqueio? O horário poderá voltar a ser oferecido.')) return;
    setError('');
    try {
      await request('/admin/blocked-times/' + block.id, { method: 'DELETE' });
      setBlocks((current) => current.filter((entry) => entry.id !== block.id));
    } catch (requestError) {
      setError(humanError(requestError));
    }
  }

  return (
    <section className="admin-view">
      <div className="admin-view__heading">
        <div><p className="eyebrow">AGENDA</p><h1>Bloquear horários</h1></div>
        <Button className="button--light" icon={RefreshCw} onClick={load} disabled={loading}>Atualizar</Button>
      </div>
      <div className="admin-two-columns">
        <form className="data-card editor-form" onSubmit={submit}>
          <h2>Novo bloqueio</h2>
          <p className="muted-copy">Use para férias, almoço, reunião ou qualquer indisponibilidade.</p>
          {error ? <Notice>{error}</Notice> : null}
          {success ? <Notice tone="success">{success}</Notice> : null}
          <label>Profissional
            <select value={form.barber_id} onChange={(event) => setForm((current) => ({ ...current, barber_id: event.target.value }))}>
              <option value="">Toda a barbearia</option>
              {barbers.map((barber) => <option key={barber.id} value={barber.id}>{barber.name}</option>)}
            </select>
          </label>
          <label>Início
            <input type="datetime-local" value={form.start_datetime} onChange={(event) => setForm((current) => ({ ...current, start_datetime: event.target.value }))} required />
          </label>
          <label>Fim
            <input type="datetime-local" value={form.end_datetime} min={form.start_datetime || undefined} onChange={(event) => setForm((current) => ({ ...current, end_datetime: event.target.value }))} required />
          </label>
          <label>Motivo <small>opcional</small>
            <input value={form.reason} onChange={(event) => setForm((current) => ({ ...current, reason: event.target.value }))} placeholder="Ex.: férias, reunião, compromisso" />
          </label>
          <Button type="submit" className="button--gold" icon={Ban} disabled={saving}>{saving ? 'Bloqueando...' : 'Bloquear período'}</Button>
        </form>
        <div className="data-card block-list">
          <h2>Indisponibilidades</h2>
          {blocks.map((block) => {
            const barber = barbers.find((person) => Number(person.id) === Number(block.barber_id));
            return (
              <article className="block-row" key={block.id}>
                <Ban size={19} />
                <div><b>{barber ? barber.name : 'Toda a barbearia'}</b><small>{formatDateTime(block.start_datetime)} até {formatDateTime(block.end_datetime)}{block.reason ? ' · ' + block.reason : ''}</small></div>
                <button type="button" onClick={() => remove(block)} aria-label="Remover bloqueio"><Trash2 size={16} /></button>
              </article>
            );
          })}
          {!loading && !blocks.length ? <div className="empty-state"><Calendar size={27} /><p>Nenhum bloqueio ativo.</p></div> : null}
        </div>
      </div>
    </section>
  );
}

function AdminShell({ token, onLogout }) {
  const [section, setSection] = useState('dashboard');
  const [menuOpen, setMenuOpen] = useState(false);
  const request = useCallback(async (path, options = {}) => {
    try {
      return await api(path, { ...options, token });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onLogout();
      throw error;
    }
  }, [token, onLogout]);

  const navigation = [
    ['dashboard', 'Visão geral', LayoutDashboard],
    ['appointments', 'Agenda', ClipboardList],
    ['customers', 'Clientes', Users],
    ['barbers', 'Barbeiros', UserCog],
    ['services', 'Serviços', Scissors],
    ['gallery', 'Galeria', ImageIcon],
    ['settings', 'Configurações', Settings],
    ['hours', 'Horários', Clock],
    ['blocks', 'Bloqueios', Ban],
  ];

  function choose(name) {
    setSection(name);
    setMenuOpen(false);
  }

  let view = <AdminDashboard request={request} />;
  if (section === 'appointments') view = <AdminAppointments request={request} />;
  if (section === 'customers') view = <AdminCustomers request={request} />;
  if (section === 'barbers') view = <EntityManager request={request} kind="barbers" />;
  if (section === 'services') view = <EntityManager request={request} kind="services" />;
  if (section === 'gallery') view = <AdminGallery request={request} />;
  if (section === 'settings') view = <AdminSettings request={request} />;
  if (section === 'hours') view = <AdminHours request={request} />;
  if (section === 'blocks') view = <AdminBlocks request={request} />;

  return (
    <div className="admin-shell">
      <aside className={'admin-sidebar' + (menuOpen ? ' admin-sidebar--open' : '')}>
        <div className="admin-sidebar__brand"><Brand compact /><small>PAINEL ADMINISTRATIVO</small></div>
        <nav aria-label="Navegação do painel">
          {navigation.map(([name, label, Icon]) => (
            <button key={name} type="button" className={section === name ? 'is-active' : ''} onClick={() => choose(name)}>
              <Icon size={18} /> {label}
            </button>
          ))}
        </nav>
        <div className="admin-sidebar__footer">
          <a href="/" target="_blank" rel="noreferrer"><ExternalLink size={15} /> Ver site</a>
          <button type="button" onClick={onLogout}><LogOut size={17} /> Sair</button>
        </div>
      </aside>
      <div className="admin-content">
        <header className="admin-mobile-header">
          <button type="button" onClick={() => setMenuOpen(!menuOpen)} aria-label="Abrir menu administrativo"><Menu size={23} /></button>
          <Brand compact />
          <button type="button" onClick={onLogout} aria-label="Sair"><LogOut size={20} /></button>
        </header>
        {view}
      </div>
    </div>
  );
}

function Admin() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || '');
  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken('');
  }, []);
  return token ? <AdminShell token={token} onLogout={logout} /> : <AdminLogin onLogin={setToken} />;
}

const root = createRoot(document.getElementById('root'));
root.render(window.location.pathname.startsWith('/admin') ? <Admin /> : <Home />);

