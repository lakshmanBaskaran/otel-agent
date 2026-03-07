begin;

truncate table public.reservations_hackathon restart identity;
truncate table public.channel_code_lookup cascade;
truncate table public.market_code_lookup cascade;
truncate table public.room_type_lookup cascade;

insert into public.room_type_lookup (space_type, room_class, display_name, number_of_rooms) values
('KS','Standard','Standard King',52),
('TB','Standard','Standard Twin',20),
('EX','Executive','Executive King',26);

insert into public.market_code_lookup (market_code, market_name, macro_group, description) values
('OTA','Online Travel Agency','Retail','Third-party online channels such as Booking.com and Expedia.'),
('BAR','Best Available Retail','Retail','Direct flexible retail business.'),
('PROM','Promotional Retail','Retail','Direct promotional and member-rate retail bookings.'),
('FIT','Free Independent Traveller','Leisure','Independent leisure demand, often direct or contracted.'),
('CSR','Corporate Negotiated','Corporate','Negotiated corporate transient business.'),
('CNR','Corporate Room Nights','Corporate','Corporate transient business via agency or negotiated accounts.'),
('CNI','Conference / Incentive Group','MICE','Group business tied to conferences or incentives.'),
('CGR','Corporate Group','MICE','Corporate group blocks and meetings business.'),
('EVEN','Event Demand','MICE','Demand associated with citywide or hotel-linked events.'),
('SMERF','SMERF Group','Leisure Group','Social, military, educational, religious, fraternal groups.');

insert into public.channel_code_lookup (channel_code, channel_name, channel_group) values
('WEB','Web / OTA Web','Digital'),
('REC','Direct Reservations / Brand Web','Direct'),
('EMA','Email / Central Reservations','Offline'),
('WAL','Walk-in','Offline');

create temporary table tmp_calc as
with nums as (
  select generate_series(1,180) as n
),
base as (
  select
    n,
    'R' || lpad(n::text, 4, '0') as reservation_id,
    case
      when n <= 45 then date '2026-04-01' + ((n * 2) % 28)
      when n <= 90 then date '2026-05-01' + ((n * 3) % 30)
      when n <= 135 then date '2026-06-01' + ((n * 2) % 29)
      else date '2026-07-01' + ((n * 2) % 30)
    end as arrival_date,
    case
      when n between 136 and 155 then 3 + (n % 2)
      when n % 17 = 0 then 4
      when n % 9 = 0 then 1
      else 2 + (n % 2)
    end as stay_length,
    case when n between 136 and 155 then true else false end as is_block,
    case
      when n between 136 and 155 then false
      when n % 41 = 0 then true
      else false
    end as is_walk_in,
    case
      when n between 136 and 145 then 'CNI'
      when n between 146 and 150 then 'CGR'
      when n between 151 and 153 then 'EVEN'
      when n between 154 and 155 then 'SMERF'
      when n between 46 and 60 then case when n % 2 = 0 then 'CSR' else 'CNR' end
      when n between 91 and 110 then case when n % 4 = 0 then 'CSR' else 'OTA' end
      when n % 5 = 0 then 'BAR'
      when n % 7 = 0 then 'FIT'
      when n % 3 = 0 then 'PROM'
      else 'OTA'
    end as market_code,
    case
      when n between 136 and 155 then 'EMA'
      when n % 41 = 0 then 'WAL'
      when n % 5 = 0 or n % 7 = 0 or n % 3 = 0 then 'REC'
      else 'WEB'
    end as channel_code,
    case
      when n % 11 = 0 then 'EX'
      when n % 4 = 0 then 'TB'
      else 'KS'
    end as space_type,
    case
      when n between 136 and 155 then 4 + (n % 9)
      when n % 37 = 0 then 2
      else 1
    end as number_of_spaces,
    case
      when n <= 20 then 75 + (n % 20)
      when n <= 45 then 35 + (n % 40)
      when n <= 60 then 70 + (n % 30)
      when n <= 90 then 12 + (n % 25)
      when n <= 110 then 95 + (n % 35)
      when n <= 135 then 5 + (n % 18)
      else 45 + (n % 70)
    end as lead_time,
    case
      when n % 29 = 0 or n between 96 and 103 or n in (58, 62, 121, 165) then 'Cancelled'
      else 'Reserved'
    end as reservation_status,
    case (n % 8)
      when 0 then 'US'
      when 1 then 'IE'
      when 2 then 'GB'
      when 3 then 'DE'
      when 4 then 'FR'
      when 5 then 'NL'
      when 6 then 'CA'
      else 'ES'
    end as guest_country,
    case
      when n between 46 and 60 then case when n % 2 = 0 then 'Acme Consulting' else 'Vertex Systems' end
      when n between 136 and 155 then case when n % 4 = 0 then 'TechSummit' when n % 4 = 1 then 'Legal Partners LLP' when n % 4 = 2 then 'Dublin Design Week' else 'Community Choir' end
      when n in (112,113,114) then 'DraftKings'
      when n in (166,167,168) then 'Barclays'
      else null
    end as company_name,
    case when n between 46 and 60 then 'TravelHub' else null end as travel_agent_name
  from nums
)
select
  reservation_id,
  arrival_date,
  arrival_date + stay_length as departure_date,
  reservation_status,
  (arrival_date - (lead_time || ' days')::interval + (n || ' hours')::interval)::timestamptz as create_datetime,
  case
    when reservation_status = 'Cancelled'
    then (arrival_date - (((n % 10) + 1) || ' days')::interval)::timestamptz
    else null::timestamptz
  end as cancellation_datetime,
  guest_country,
  is_block,
  is_walk_in,
  number_of_spaces,
  space_type,
  market_code,
  channel_code,
  lead_time,
  company_name,
  travel_agent_name,
  case
    when channel_code = 'WAL' then 'Walk-in'
    when market_code = 'OTA' and n % 2 = 0 then 'Booking.com'
    when market_code = 'OTA' then 'Expedia'
    when channel_code = 'EMA' then 'OCC Central Reservations'
    when market_code in ('BAR','PROM','FIT') and n % 3 = 0 then 'Members Rate booking'
    when channel_code = 'REC' then 'Brand website'
    else 'Sabre'
  end as source_name,
  case
    when market_code in ('CNI','CGR','EVEN','SMERF') then 'GROUPBB'
    when market_code = 'CSR' then case when n % 2 = 0 then 'CORP10BB' else 'BARCBB' end
    when market_code = 'CNR' then 'GOORO'
    when market_code = 'FIT' then 'FITBB'
    when market_code = 'PROM' then case when n % 2 = 0 then 'OCHEARLY' else 'OCHPERKRO' end
    when market_code = 'BAR' then case when n % 2 = 0 then 'DLY1' else 'DLYBB' end
    when market_code = 'OTA' and channel_code = 'WEB' and n % 2 = 0
      then case when n % 3 = 0 then 'BOOKBAR' when n % 3 = 1 then 'BOOKBARB' else 'BOOKPROM' end
    when market_code = 'OTA'
      then case when n % 3 = 0 then 'EXPP' when n % 3 = 1 then 'EXPBARB' else 'EXPBARH' end
    else 'DLY1'
  end as rate_plan_code,
  round((
    case space_type
      when 'EX' then 245
      when 'TB' then 172
      else 185
    end
    + case market_code
        when 'OTA' then -18
        when 'BAR' then 12
        when 'PROM' then -10
        when 'FIT' then 20
        when 'CSR' then 8
        when 'CNR' then 4
        when 'CNI' then -22
        when 'CGR' then -24
        when 'EVEN' then -15
        when 'SMERF' then -28
        else 0
      end
    + case
        when arrival_date between date '2026-07-10' and date '2026-07-22' then 18
        when arrival_date between date '2026-06-08' and date '2026-06-28' then -8
        else 0
      end
    + ((n % 7) * 3)
  )::numeric, 2) as adr_room,
  stay_length as nights
from base;

insert into public.reservations_hackathon (
  reservation_id,
  arrival_date,
  departure_date,
  stay_date,
  reservation_status,
  create_datetime,
  cancellation_datetime,
  guest_country,
  is_block,
  is_walk_in,
  number_of_spaces,
  space_type,
  market_code,
  channel_code,
  source_name,
  rate_plan_code,
  daily_room_revenue_before_tax,
  daily_total_revenue_before_tax,
  nights,
  adr_room,
  lead_time,
  company_name,
  travel_agent_name
)
select
  c.reservation_id,
  c.arrival_date,
  c.departure_date,
  gs::date as stay_date,
  c.reservation_status,
  c.create_datetime,
  c.cancellation_datetime,
  c.guest_country,
  c.is_block,
  c.is_walk_in,
  c.number_of_spaces,
  c.space_type,
  c.market_code,
  c.channel_code,
  c.source_name,
  c.rate_plan_code,
  round(c.adr_room * c.number_of_spaces, 2) as daily_room_revenue_before_tax,
  round(
    (c.adr_room * c.number_of_spaces) +
    case
      when c.rate_plan_code like '%BB%' or c.market_code in ('FIT','CNI','CGR','EVEN','SMERF')
      then 18 * c.number_of_spaces
      else 0
    end,
    2
  ) as daily_total_revenue_before_tax,
  c.nights,
  c.adr_room,
  c.lead_time,
  c.company_name,
  c.travel_agent_name
from tmp_calc c
cross join lateral generate_series(
  c.arrival_date,
  c.departure_date - interval '1 day',
  interval '1 day'
) gs;

drop table if exists tmp_calc;

commit;
