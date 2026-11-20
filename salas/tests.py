from datetime import timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Organizacao, Perfil
from .models import Sala, Reserva


class Base(TestCase):
    # Duas organizações, com usuário, operador e administrador
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organizacao.objects.create(nome="Org A")
        cls.org_b = Organizacao.objects.create(nome="Org B")
        cls.usuario = cls.cria_usuario('usuario', cls.org_a, Perfil.USUARIO)
        cls.outro = cls.cria_usuario('outro', cls.org_a, Perfil.USUARIO)
        cls.operador = cls.cria_usuario('operador', cls.org_a, Perfil.OPERADOR)
        cls.admin = cls.cria_usuario('admin', cls.org_a, Perfil.ADMINISTRADOR)
        cls.usuario_b = cls.cria_usuario('usuario_b', cls.org_b, Perfil.USUARIO)
        cls.sala = Sala.objects.create(organizacao=cls.org_a, nome="Sala 1", capacidade=10)
        cls.sala_aprov = Sala.objects.create(
            organizacao=cls.org_a, nome="Sala Diretoria", capacidade=6, exige_aprovacao=True,
        )
        cls.sala_b = Sala.objects.create(organizacao=cls.org_b, nome="Sala B", capacidade=8)

    @staticmethod
    def cria_usuario(nome, org, papel):
        user = User.objects.create_user(nome, password='senha-teste-123')
        Perfil.objects.create(usuario=user, organizacao=org, papel=papel)
        return user

    def reserva(self, dono, horas, sala=None, status='confirmada'):
        inicio = timezone.now() + timedelta(hours=horas)
        sala = sala or self.sala
        return Reserva.objects.create(
            organizacao=sala.organizacao, sala=sala, responsavel=dono.username,
            data_inicio=inicio, data_fim=inicio + timedelta(hours=1),
            status=status, criado_por=dono,
        )

    @staticmethod
    def local(dt):
        return timezone.localtime(dt).strftime('%Y-%m-%dT%H:%M')

    def dados_form(self, sala, horas):
        inicio = timezone.now() + timedelta(hours=horas)
        return {
            'sala': sala.id, 'responsavel': 'Fulano',
            'data_inicio': self.local(inicio),
            'data_fim': self.local(inicio + timedelta(hours=1)),
            'descricao': '', 'recorrencia': '',
        }


# ===== TELAS =====

class TelasSalasTest(Base):
    def test_usuario_nao_cria_edita_nem_apaga_sala(self):
        self.client.force_login(self.usuario)
        dados = {'nome': 'Nova', 'capacidade': 5, 'descricao': ''}
        self.assertEqual(self.client.post(reverse('criar_sala'), dados).status_code, 403)
        self.assertEqual(self.client.post(reverse('editar_sala', args=[self.sala.id]), dados).status_code, 403)
        self.assertEqual(self.client.post(reverse('deletar_sala', args=[self.sala.id])).status_code, 403)
        self.assertFalse(Sala.objects.filter(nome='Nova').exists())
        self.assertTrue(Sala.objects.filter(id=self.sala.id).exists())

    def test_operador_e_admin_criam_sala(self):
        for user, nome in [(self.operador, 'Sala Op'), (self.admin, 'Sala Adm')]:
            self.client.force_login(user)
            resp = self.client.post(reverse('criar_sala'), {'nome': nome, 'capacidade': 5, 'descricao': ''})
            self.assertEqual(resp.status_code, 302)
            self.assertTrue(Sala.objects.filter(nome=nome, organizacao=self.org_a).exists())

    def test_botoes_de_sala_escondidos_para_usuario(self):
        self.client.force_login(self.usuario)
        self.assertNotContains(self.client.get(reverse('lista_salas')), reverse('criar_sala'))
        self.client.force_login(self.operador)
        self.assertContains(self.client.get(reverse('lista_salas')), reverse('criar_sala'))


class TelasReservasTest(Base):
    def test_reserva_em_sala_comum_nasce_confirmada_com_dono(self):
        self.client.force_login(self.usuario)
        resp = self.client.post(reverse('criar_reserva'), self.dados_form(self.sala, 48))
        self.assertEqual(resp.status_code, 302)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.status, 'confirmada')
        self.assertEqual(reserva.criado_por, self.usuario)

    def test_status_enviado_no_form_e_ignorado(self):
        self.client.force_login(self.usuario)
        dados = self.dados_form(self.sala, 48) | {'status': 'cancelada'}
        self.client.post(reverse('criar_reserva'), dados)
        self.assertEqual(Reserva.objects.get().status, 'confirmada')

    def test_sala_com_aprovacao_nasce_pendente_e_operador_aprova(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse('criar_reserva'), self.dados_form(self.sala_aprov, 48))
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.status, 'pendente')
        # Usuário não aprova
        self.assertEqual(self.client.post(reverse('aprovar_reserva', args=[reserva.id])).status_code, 403)
        self.client.force_login(self.operador)
        self.client.post(reverse('aprovar_reserva', args=[reserva.id]))
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, 'confirmada')

    def test_operador_recusa_pendente(self):
        reserva = self.reserva(self.usuario, 48, sala=self.sala_aprov, status='pendente')
        self.client.force_login(self.operador)
        self.client.post(reverse('recusar_reserva', args=[reserva.id]))
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, 'cancelada')

    def test_usuario_cancela_propria_com_mais_de_24h(self):
        reserva = self.reserva(self.usuario, 48)
        self.client.force_login(self.usuario)
        resp = self.client.post(reverse('cancelar_reserva', args=[reserva.id]))
        self.assertEqual(resp.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, 'cancelada')
        self.assertTrue(Reserva.objects.filter(id=reserva.id).exists())  # cancela, não apaga

    def test_usuario_nao_cancela_nem_edita_com_menos_de_24h(self):
        reserva = self.reserva(self.usuario, 5)
        self.client.force_login(self.usuario)
        resp = self.client.post(reverse('cancelar_reserva', args=[reserva.id]))
        self.assertContains(resp, Reserva.MSG_24H)
        resp = self.client.post(reverse('editar_reserva', args=[reserva.id]), self.dados_form(self.sala, 72))
        self.assertContains(resp, Reserva.MSG_24H)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, 'confirmada')
        self.assertLess(reserva.data_inicio, timezone.now() + timedelta(hours=6))

    def test_usuario_nao_cancela_nem_edita_reserva_de_outro(self):
        reserva = self.reserva(self.outro, 48)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post(reverse('cancelar_reserva', args=[reserva.id])).status_code, 403)
        self.assertEqual(self.client.get(reverse('editar_reserva', args=[reserva.id])).status_code, 403)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, 'confirmada')

    def test_operador_cancela_com_menos_de_24h(self):
        reserva = self.reserva(self.usuario, 2)
        self.client.force_login(self.operador)
        self.assertEqual(self.client.post(reverse('cancelar_reserva', args=[reserva.id])).status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, 'cancelada')

    def test_apagar_de_vez_so_operador(self):
        reserva = self.reserva(self.usuario, 48)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post(reverse('deletar_reserva', args=[reserva.id])).status_code, 403)
        self.client.force_login(self.admin)
        self.client.post(reverse('deletar_reserva', args=[reserva.id]))
        self.assertFalse(Reserva.objects.filter(id=reserva.id).exists())

    def test_horario_cancelado_volta_a_ficar_livre(self):
        reserva = self.reserva(self.outro, 48)
        self.client.force_login(self.usuario)
        dados = {
            'sala': self.sala.id, 'responsavel': 'Fulano',
            'data_inicio': self.local(reserva.data_inicio),
            'data_fim': self.local(reserva.data_fim),
            'descricao': '', 'recorrencia': '',
        }
        self.assertContains(self.client.post(reverse('criar_reserva'), dados, follow=True), 'Conflito')
        reserva.status = 'cancelada'
        reserva.save()
        self.assertEqual(self.client.post(reverse('criar_reserva'), dados).status_code, 302)
        self.assertEqual(Reserva.objects.filter(status='confirmada').count(), 1)

    def test_botoes_da_lista_conforme_papel(self):
        propria = self.reserva(self.usuario, 48)
        de_outro = self.reserva(self.outro, 72)
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('lista_reservas'))
        self.assertContains(resp, reverse('cancelar_reserva', args=[propria.id]))
        self.assertNotContains(resp, reverse('cancelar_reserva', args=[de_outro.id]))
        self.assertNotContains(resp, reverse('deletar_reserva', args=[propria.id]))

    def test_isolamento_entre_organizacoes(self):
        reserva = self.reserva(self.usuario, 48)
        self.client.force_login(self.usuario_b)
        self.assertEqual(self.client.get(reverse('detalhes_reserva', args=[reserva.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse('cancelar_reserva', args=[reserva.id])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('lista_reservas')), 'Sala 1')
        # Operador da org A também não enxerga a org B
        reserva_b = self.reserva(self.usuario_b, 48, sala=self.sala_b)
        self.client.force_login(self.operador)
        self.assertEqual(self.client.post(reverse('cancelar_reserva', args=[reserva_b.id])).status_code, 404)


# ===== API =====

class ApiTest(Base):
    def setUp(self):
        self.api = APIClient()

    def como(self, user):
        self.api.force_authenticate(user)
        return self.api

    def dados_api(self, sala, horas):
        inicio = timezone.now() + timedelta(hours=horas)
        return {
            'sala': sala.id, 'responsavel': 'Fulano',
            'data_inicio': inicio.isoformat(), 'data_fim': (inicio + timedelta(hours=1)).isoformat(),
        }

    def test_usuario_nao_cria_sala_pela_api(self):
        resp = self.como(self.usuario).post('/api/salas/', {'nome': 'X', 'capacidade': 5})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.como(self.usuario).get('/api/salas/').status_code, 200)
        resp = self.como(self.operador).post('/api/salas/', {'nome': 'X', 'capacidade': 5})
        self.assertEqual(resp.status_code, 201)

    def test_reserva_pela_api_nasce_confirmada_com_dono(self):
        dados = self.dados_api(self.sala, 48) | {'status': 'cancelada'}
        resp = self.como(self.usuario).post('/api/reservas/', dados)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['status'], 'confirmada')
        self.assertEqual(resp.data['criado_por'], self.usuario.id)

    def test_aprovacao_pela_api(self):
        resp = self.como(self.usuario).post('/api/reservas/', self.dados_api(self.sala_aprov, 48))
        self.assertEqual(resp.data['status'], 'pendente')
        id_ = resp.data['id']
        self.assertEqual(self.como(self.usuario).post(f'/api/reservas/{id_}/aprovar/').status_code, 403)
        resp = self.como(self.operador).post(f'/api/reservas/{id_}/aprovar/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'confirmada')

    def test_cancelamento_pela_api(self):
        propria = self.reserva(self.usuario, 48)
        em_cima = self.reserva(self.usuario, 5)
        de_outro = self.reserva(self.outro, 72)
        api = self.como(self.usuario)
        self.assertEqual(api.post(f'/api/reservas/{propria.id}/cancelar/').status_code, 200)
        resp = api.post(f'/api/reservas/{em_cima.id}/cancelar/')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data['detail'], Reserva.MSG_24H)
        self.assertEqual(api.post(f'/api/reservas/{de_outro.id}/cancelar/').status_code, 403)
        self.assertEqual(self.como(self.operador).post(f'/api/reservas/{em_cima.id}/cancelar/').status_code, 200)
        statuses = dict(Reserva.objects.values_list('id', 'status'))
        self.assertEqual(statuses, {propria.id: 'cancelada', em_cima.id: 'cancelada', de_outro.id: 'confirmada'})

    def test_edicao_e_exclusao_pela_api(self):
        propria = self.reserva(self.usuario, 48)
        em_cima = self.reserva(self.usuario, 5)
        api = self.como(self.usuario)
        self.assertEqual(api.patch(f'/api/reservas/{propria.id}/', {'responsavel': 'Novo'}).status_code, 200)
        self.assertEqual(api.patch(f'/api/reservas/{em_cima.id}/', {'responsavel': 'Novo'}).status_code, 403)
        self.assertEqual(api.delete(f'/api/reservas/{propria.id}/').status_code, 403)
        self.assertEqual(self.como(self.operador).patch(f'/api/reservas/{em_cima.id}/', {'responsavel': 'Op'}).status_code, 200)
        self.assertEqual(self.como(self.operador).delete(f'/api/reservas/{propria.id}/').status_code, 204)

    def test_horario_cancelado_livre_pela_api(self):
        reserva = self.reserva(self.outro, 48)
        dados = {'sala': self.sala.id, 'responsavel': 'X',
                 'data_inicio': reserva.data_inicio.isoformat(), 'data_fim': reserva.data_fim.isoformat()}
        self.assertEqual(self.como(self.usuario).post('/api/reservas/', dados).status_code, 400)
        self.como(self.operador).post(f'/api/reservas/{reserva.id}/cancelar/')
        self.assertEqual(self.como(self.usuario).post('/api/reservas/', dados).status_code, 201)

    def test_isolamento_pela_api(self):
        reserva = self.reserva(self.usuario, 48)
        api = self.como(self.usuario_b)
        self.assertEqual(api.get(f'/api/reservas/{reserva.id}/').status_code, 404)
        self.assertEqual(api.post(f'/api/reservas/{reserva.id}/cancelar/').status_code, 404)
        self.assertEqual(api.get('/api/reservas/').data, [])
        self.assertEqual(api.post('/api/reservas/', self.dados_api(self.sala, 48)).status_code, 400)


# ===== MIGRAÇÃO =====

class MigracaoPapelTest(TransactionTestCase):
    def test_perfis_existentes_viram_administrador(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('core', '0001_initial')])
        apps = executor.loader.project_state([('core', '0001_initial')]).apps
        org = apps.get_model('core', 'Organizacao').objects.create(nome='Antiga')
        user = apps.get_model('auth', 'User').objects.create(username='antigo')
        apps.get_model('core', 'Perfil').objects.create(usuario=user, organizacao=org)

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        self.assertEqual(Perfil.objects.get(usuario__username='antigo').papel, 'administrador')


# ===== ADMIN: TIPO DE USUÁRIO =====

class AdminTipoUsuarioTest(TestCase):
    URL_ADD = '/admin/auth/user/add/'

    @classmethod
    def setUpTestData(cls):
        cls.org = Organizacao.objects.create(nome="Org Admin")
        cls.super = User.objects.create_superuser('chefe', password='senha-teste-123')

    def setUp(self):
        self.client.force_login(self.super)

    def cria(self, nome, tipo, org=None):
        dados = {
            'username': nome, 'password1': 'Senha-Forte-987', 'password2': 'Senha-Forte-987',
            'tipo_usuario': tipo, 'organizacao': org.id if org else '',
        }
        return self.client.post(self.URL_ADD, dados)

    def confere(self, nome, papel, staff):
        user = User.objects.get(username=nome)
        self.assertEqual(user.is_staff, staff)
        self.assertEqual(user.is_superuser, staff)
        self.assertTrue(user.check_password('Senha-Forte-987'))  # senha com criptografia
        self.assertNotEqual(user.password, 'Senha-Forte-987')
        if papel:
            self.assertEqual(user.perfil.papel, papel)
            self.assertEqual(user.perfil.organizacao, self.org)
        # Acesso ao Admin só para Administrador
        self.client.force_login(user)
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200 if staff else 302)
        self.client.force_login(self.super)

    def test_tela_de_adicionar_tem_tudo_numa_tela(self):
        resp = self.client.get(self.URL_ADD)
        for campo in ['username', 'password1', 'password2', 'tipo_usuario', 'organizacao']:
            self.assertContains(resp, f'name="{campo}"')
        self.assertContains(resp, 'Funcionário')

    def test_cria_usuario(self):
        self.assertEqual(self.cria('u1', 'usuario', self.org).status_code, 302)
        self.confere('u1', 'usuario', staff=False)

    def test_cria_funcionario(self):
        self.assertEqual(self.cria('f1', 'operador', self.org).status_code, 302)
        self.confere('f1', 'operador', staff=False)

    def test_cria_administrador_com_e_sem_organizacao(self):
        self.assertEqual(self.cria('a1', 'administrador', self.org).status_code, 302)
        self.confere('a1', 'administrador', staff=True)
        self.assertEqual(self.cria('a2', 'administrador').status_code, 302)
        self.confere('a2', None, staff=True)
        self.assertFalse(Perfil.objects.filter(usuario__username='a2').exists())

    def test_organizacao_obrigatoria_para_usuario_e_funcionario(self):
        for nome, tipo in [('sem1', 'usuario'), ('sem2', 'operador')]:
            resp = self.cria(nome, tipo)
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Escolha a organização para Usuário e Funcionário.")
            self.assertFalse(User.objects.filter(username=nome).exists())

    def test_edicao_marca_o_tipo_e_corrige_admin_sem_superusuario(self):
        user = User.objects.create_user('antigo', password='x')
        Perfil.objects.create(usuario=user, organizacao=self.org, papel=Perfil.ADMINISTRADOR)
        url = f'/admin/auth/user/{user.id}/change/'
        resp = self.client.get(url)
        self.assertEqual(resp.context['adminform'].form['tipo_usuario'].value(), 'operador')
        dados = {
            'username': 'antigo', 'email': '', 'first_name': '', 'last_name': '',
            'is_active': 'on', 'tipo_usuario': resp.context['adminform'].form['tipo_usuario'].value(),
            'organizacao': self.org.id,
        }
        self.assertEqual(self.client.post(url, dados).status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.perfil.papel, 'operador')
        self.assertFalse(user.is_staff)
        # Superusuário aparece como Administrador
        resp = self.client.get(f'/admin/auth/user/{self.super.id}/change/')
        self.assertEqual(resp.context['adminform'].form['tipo_usuario'].value(), 'administrador')


# ===== CADASTRO PÚBLICO =====

class CadastroTest(TestCase):
    URL = '/contas/cadastro/'

    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organizacao.objects.create(nome="Org A")
        cls.org_b = Organizacao.objects.create(nome="Org B")
        cls.sala = Sala.objects.create(organizacao=cls.org_b, nome="Sala B1", capacidade=5)

    def dados(self, **extra):
        return {
            'username': 'novo', 'email': 'novo@example.com',
            'password1': 'Senha-Forte-987', 'password2': 'Senha-Forte-987',
            'organizacao': self.org_b.id, **extra,
        }

    def test_cadastro_cria_usuario_comum_logado(self):
        resp = self.client.post(self.URL, self.dados(), follow=True)
        self.assertRedirects(resp, reverse('lista_salas'))
        self.assertContains(resp, 'Conta criada! Você já pode reservar salas.')
        user = User.objects.get(username='novo')
        self.assertEqual(user.email, 'novo@example.com')
        self.assertTrue(user.check_password('Senha-Forte-987'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.perfil.papel, Perfil.USUARIO)
        self.assertEqual(user.perfil.organizacao, self.org_b)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.id)
        # Sem acesso ao Admin
        self.assertEqual(self.client.get('/admin/').status_code, 302)

    def test_post_forjado_nao_muda_o_acesso(self):
        forjado = self.dados(
            is_staff='on', is_superuser='on', papel='administrador',
            tipo_usuario='administrador', groups='1',
        )
        self.client.post(self.URL, forjado)
        user = User.objects.get(username='novo')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.perfil.papel, Perfil.USUARIO)

    def test_senhas_diferentes_mostram_erro(self):
        resp = self.client.post(self.URL, self.dados(password2='Outra-Senha-123'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['form'].errors.get('password2'))
        self.assertFalse(User.objects.filter(username='novo').exists())

    def test_organizacao_obrigatoria(self):
        resp = self.client.post(self.URL, self.dados(organizacao=''))
        self.assertTrue(resp.context['form'].errors.get('organizacao'))
        self.assertFalse(User.objects.filter(username='novo').exists())

    def test_uma_organizacao_so_ja_vem_selecionada(self):
        # A migração 0003 cria a "Organização padrão"; deixa só a org B
        Organizacao.objects.exclude(pk=self.org_b.pk).delete()
        resp = self.client.get(self.URL)
        self.assertEqual(resp.context['form']['organizacao'].value(), self.org_b.id)

    def test_logado_vai_para_lista_de_salas(self):
        user = User.objects.create_user('ja', password='x')
        self.client.force_login(user)
        self.assertRedirects(self.client.get(self.URL), reverse('lista_salas'), fetch_redirect_response=False)

    def test_links_entre_login_e_cadastro(self):
        self.assertContains(self.client.get(reverse('login')), self.URL)
        self.assertContains(self.client.get(self.URL), reverse('login'))

    def test_recem_cadastrado_nao_cria_sala_mas_reserva(self):
        self.client.post(self.URL, self.dados())
        resp = self.client.post(reverse('criar_sala'), {'nome': 'X', 'capacidade': 3, 'descricao': ''})
        self.assertEqual(resp.status_code, 403)
        inicio = timezone.now() + timedelta(hours=48)
        resp = self.client.post(reverse('criar_reserva'), {
            'sala': self.sala.id, 'responsavel': 'Novo',
            'data_inicio': Base.local(inicio), 'data_fim': Base.local(inicio + timedelta(hours=1)),
            'descricao': '', 'recorrencia': '',
        })
        self.assertEqual(resp.status_code, 302)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.criado_por.username, 'novo')
        self.assertEqual(reserva.status, 'confirmada')
