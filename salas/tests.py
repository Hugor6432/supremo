import calendar
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Organizacao, Perfil, RegistroAtividade
from .models import Recurso, Sala, Reserva


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
            'sala': sala.id,
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
            dados = {'nome': nome, 'capacidade': 5, 'descricao': ''} | RecursosTest.gestao(0)
            resp = self.client.post(reverse('criar_sala'), dados)
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
            'sala': self.sala.id,
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
            'sala': sala.id,
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
        self.assertEqual(api.patch(f'/api/reservas/{propria.id}/', {'descricao': 'Novo'}).status_code, 200)
        self.assertEqual(api.patch(f'/api/reservas/{em_cima.id}/', {'descricao': 'Novo'}).status_code, 403)
        self.assertEqual(api.delete(f'/api/reservas/{propria.id}/').status_code, 403)
        self.assertEqual(self.como(self.operador).patch(f'/api/reservas/{em_cima.id}/', {'descricao': 'Op'}).status_code, 200)
        self.assertEqual(self.como(self.operador).delete(f'/api/reservas/{propria.id}/').status_code, 204)

    def test_horario_cancelado_livre_pela_api(self):
        reserva = self.reserva(self.outro, 48)
        dados = {'sala': self.sala.id,
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
            'sala': self.sala.id,
            'data_inicio': Base.local(inicio), 'data_fim': Base.local(inicio + timedelta(hours=1)),
            'descricao': '', 'recorrencia': '',
        })
        self.assertEqual(resp.status_code, 302)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.criado_por.username, 'novo')
        self.assertEqual(reserva.status, 'confirmada')


# ===== RESPONSÁVEL VEM DA CONTA =====

class ResponsavelDaContaTest(Base):
    def setUp(self):
        self.joao = User.objects.create_user('joao', email='joao@email.com', password='x')
        Perfil.objects.create(usuario=self.joao, organizacao=self.org_a, papel=Perfil.USUARIO)

    def test_reserva_criada_mostra_usuario_e_email(self):
        self.client.force_login(self.joao)
        dados = self.dados_form(self.sala, 48) | {'responsavel': 'Nome forjado'}
        self.assertEqual(self.client.post(reverse('criar_reserva'), dados).status_code, 302)
        reserva = Reserva.objects.get()
        # Preenchido sozinho com o nome de usuário, ignorando o valor enviado
        self.assertEqual(reserva.responsavel, 'joao')
        self.assertEqual(reserva.criado_por, self.joao)
        esperado = 'joao · joao@email.com'
        self.assertContains(self.client.get(reverse('lista_reservas')), esperado)
        self.assertContains(self.client.get(reverse('detalhes_reserva', args=[reserva.id])), esperado)
        self.assertContains(self.client.get(reverse('cancelar_reserva', args=[reserva.id])), esperado)
        self.client.force_login(self.operador)
        self.assertContains(self.client.get(reverse('deletar_reserva', args=[reserva.id])), esperado)

    def test_formulario_nao_tem_mais_o_campo_responsavel(self):
        self.client.force_login(self.joao)
        self.assertNotContains(self.client.get(reverse('criar_reserva')), 'name="responsavel"')

    def test_sem_email_e_reserva_antiga(self):
        reserva = self.reserva(self.usuario, 48)  # usuário sem e-mail
        self.assertEqual(reserva.responsavel_exibicao, 'usuario · sem e-mail')
        antiga = self.reserva(self.usuario, 72)
        Reserva.objects.filter(pk=antiga.pk).update(criado_por=None, responsavel='Texto antigo')
        antiga.refresh_from_db()
        self.client.force_login(self.operador)
        resp = self.client.get(reverse('lista_reservas'))
        self.assertContains(resp, 'usuario · sem e-mail')
        self.assertContains(resp, 'Texto antigo')

    def test_api_preenche_responsavel_e_devolve_conta(self):
        api = APIClient()
        api.force_authenticate(self.joao)
        inicio = timezone.now() + timedelta(hours=48)
        resp = api.post('/api/reservas/', {
            'sala': self.sala.id, 'responsavel': 'Nome forjado',
            'data_inicio': inicio.isoformat(), 'data_fim': (inicio + timedelta(hours=1)).isoformat(),
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['responsavel'], 'joao')
        self.assertEqual(resp.data['criado_por_usuario'], 'joao')
        self.assertEqual(resp.data['criado_por_email'], 'joao@email.com')
        detalhe = api.get(f"/api/reservas/{resp.data['id']}/").data
        self.assertEqual((detalhe['criado_por_usuario'], detalhe['criado_por_email']), ('joao', 'joao@email.com'))

    def test_admin_mostra_colunas_e_busca_por_usuario_e_email(self):
        self.reserva(self.joao, 48)
        self.reserva(self.outro, 72)
        chefe = User.objects.create_superuser('chefe', password='x')
        self.client.force_login(chefe)
        resp = self.client.get('/admin/salas/reserva/')
        self.assertContains(resp, 'Reservado por')
        self.assertContains(resp, 'joao@email.com')
        for termo in ['joao', 'joao@email.com']:
            resp = self.client.get('/admin/salas/reserva/', {'q': termo})
            self.assertEqual(resp.context['cl'].result_count, 1, termo)


# ===== RECURSOS NO CADASTRO DA SALA =====

class RecursosTest(Base):
    @staticmethod
    def gestao(total, iniciais=0):
        return {
            'recursos-TOTAL_FORMS': str(total), 'recursos-INITIAL_FORMS': str(iniciais),
            'recursos-MIN_NUM_FORMS': '0', 'recursos-MAX_NUM_FORMS': '1000',
        }

    def test_funcionario_cria_sala_com_dois_recursos(self):
        self.client.force_login(self.operador)
        dados = {'nome': 'Lab', 'capacidade': 20, 'descricao': ''} | self.gestao(3) | {
            'recursos-0-nome': 'Projetor', 'recursos-0-descricao': 'Full HD',
            'recursos-1-nome': 'Quadro', 'recursos-1-descricao': '',
            'recursos-2-nome': '', 'recursos-2-descricao': '',  # linha em branco
        }
        self.assertEqual(self.client.post(reverse('criar_sala'), dados).status_code, 302)
        sala = Sala.objects.get(nome='Lab')
        self.assertEqual(sorted(sala.recursos.values_list('nome', flat=True)), ['Projetor', 'Quadro'])
        self.assertEqual(set(sala.recursos.values_list('organizacao_id', flat=True)), {self.org_a.id})
        self.assertEqual(sala.recursos.get(nome='Projetor').descricao, 'Full HD')

    def test_funcionario_edita_um_recurso_e_remove_outro(self):
        projetor = Recurso.objects.create(organizacao=self.org_a, sala=self.sala, nome='Projetor')
        tv = Recurso.objects.create(organizacao=self.org_a, sala=self.sala, nome='TV')
        self.client.force_login(self.operador)
        dados = {'nome': self.sala.nome, 'capacidade': self.sala.capacidade, 'descricao': ''} | self.gestao(3, 2) | {
            'recursos-0-id': projetor.id, 'recursos-0-nome': 'Projetor 4K', 'recursos-0-descricao': '',
            'recursos-1-id': tv.id, 'recursos-1-nome': 'TV', 'recursos-1-descricao': '', 'recursos-1-DELETE': 'on',
            'recursos-2-nome': '', 'recursos-2-descricao': '',
        }
        resp = self.client.post(reverse('editar_sala', args=[self.sala.id]), dados)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(list(self.sala.recursos.values_list('nome', flat=True)), ['Projetor 4K'])
        self.assertFalse(Recurso.objects.filter(id=tv.id).exists())

    def test_erro_em_recurso_nao_salva_nada(self):
        self.client.force_login(self.operador)
        dados = {'nome': 'Sala Nova', 'capacidade': 5, 'descricao': ''} | self.gestao(1) | {
            'recursos-0-nome': '', 'recursos-0-descricao': 'Sem nome',
        }
        resp = self.client.post(reverse('criar_sala'), dados)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['formset'].errors[0].get('nome'))
        self.assertFalse(Sala.objects.filter(nome='Sala Nova').exists())
        self.assertFalse(Recurso.objects.exists())

    def test_nao_edita_recurso_de_outra_sala(self):
        de_outra = Recurso.objects.create(organizacao=self.org_a, sala=self.sala_aprov, nome='Café')
        self.client.force_login(self.operador)
        dados = {'nome': self.sala.nome, 'capacidade': self.sala.capacidade, 'descricao': ''} | self.gestao(1, 1) | {
            'recursos-0-id': de_outra.id, 'recursos-0-nome': 'Trocado', 'recursos-0-descricao': '',
        }
        # O Django ignora o id que não é desta sala: nada muda e nada é criado
        self.client.post(reverse('editar_sala', args=[self.sala.id]), dados)
        de_outra.refresh_from_db()
        self.assertEqual((de_outra.nome, de_outra.sala_id), ('Café', self.sala_aprov.id))
        self.assertFalse(self.sala.recursos.exists())

    def test_usuario_comum_recebe_403(self):
        self.client.force_login(self.usuario)
        dados = {'nome': 'X', 'capacidade': 5, 'descricao': ''} | self.gestao(1) | {'recursos-0-nome': 'Projetor'}
        self.assertEqual(self.client.get(reverse('criar_sala')).status_code, 403)
        self.assertEqual(self.client.post(reverse('criar_sala'), dados).status_code, 403)
        self.assertEqual(self.client.get(reverse('editar_sala', args=[self.sala.id])).status_code, 403)
        self.assertEqual(self.client.post(reverse('editar_sala', args=[self.sala.id]), dados).status_code, 403)
        self.assertFalse(Recurso.objects.exists())

    def test_recurso_criado_aparece_no_filtro_da_lista(self):
        self.client.force_login(self.operador)
        dados = {'nome': 'Lab', 'capacidade': 20, 'descricao': ''} | self.gestao(1) | {
            'recursos-0-nome': 'Impressora 3D', 'recursos-0-descricao': '',
        }
        self.client.post(reverse('criar_sala'), dados)
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('lista_salas'))
        self.assertContains(resp, '<option value="Impressora 3D"')
        filtrada = self.client.get(reverse('lista_salas'), {'recurso': 'Impressora 3D'})
        self.assertEqual([s.nome for s in filtrada.context['salas']], ['Lab'])

    def test_telas_sem_aviso_do_admin_e_com_botao_de_adicionar(self):
        self.client.force_login(self.operador)
        for url in [reverse('criar_sala'), reverse('editar_sala', args=[self.sala.id])]:
            resp = self.client.get(url)
            self.assertNotContains(resp, 'Admin → Salas')
            self.assertContains(resp, 'id="adicionar-recurso"')
            self.assertContains(resp, 'recursos-__prefix__-nome')


# ===== EXCLUSÃO REGISTRADA =====

class ExclusaoSuaveTest(Base):
    def test_funcionario_exclui_reserva_pelo_site(self):
        reserva = self.reserva(self.usuario, 48)
        self.client.force_login(self.operador)
        self.assertEqual(self.client.post(reverse('deletar_reserva', args=[reserva.id])).status_code, 302)
        # Some do site e da API
        self.assertFalse(Reserva.objects.filter(id=reserva.id).exists())
        self.assertEqual(self.client.get(reverse('detalhes_reserva', args=[reserva.id])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('lista_reservas')), reverse('detalhes_reserva', args=[reserva.id]))
        api = APIClient()
        api.force_authenticate(self.operador)
        self.assertEqual(api.get('/api/reservas/').data, [])
        self.assertEqual(api.get(f'/api/reservas/{reserva.id}/').status_code, 404)
        # Continua no banco, com quem excluiu
        guardada = Reserva.todos.get(id=reserva.id)
        self.assertEqual(guardada.excluida_por, self.operador)
        self.assertIsNotNone(guardada.excluida_em)

    def test_funcionario_exclui_sala_pelo_site(self):
        Recurso.objects.create(organizacao=self.org_a, sala=self.sala, nome='Projetor')
        reserva = self.reserva(self.usuario, 48)
        self.client.force_login(self.operador)
        self.assertEqual(self.client.post(reverse('deletar_sala', args=[self.sala.id])).status_code, 302)
        guardada = Sala.todos.get(id=self.sala.id)
        self.assertEqual(guardada.excluida_por, self.operador)
        self.assertTrue(Reserva.todos.filter(id=reserva.id).exists())
        # Some da lista, do filtro de recursos, do formulário de reserva e da API
        lista = self.client.get(reverse('lista_salas'))
        self.assertNotIn(self.sala, list(lista.context['salas']))
        self.assertNotIn('Projetor', list(lista.context['recursos']))
        form = self.client.get(reverse('criar_reserva')).context['form']
        self.assertNotIn(self.sala, form.fields['sala'].queryset)
        self.assertEqual(self.client.get(reverse('editar_sala', args=[self.sala.id])).status_code, 404)
        # As reservas dessa sala também somem
        self.assertFalse(Reserva.objects.filter(id=reserva.id).exists())
        api = APIClient()
        api.force_authenticate(self.operador)
        self.assertNotIn(self.sala.id, [s['id'] for s in api.get('/api/salas/').data])
        dados = {'sala': self.sala.id, 'data_inicio': (timezone.now() + timedelta(hours=60)).isoformat(),
                 'data_fim': (timezone.now() + timedelta(hours=61)).isoformat()}
        self.assertEqual(api.post('/api/reservas/', dados).status_code, 400)

    def test_horario_de_reserva_excluida_fica_livre(self):
        reserva = self.reserva(self.outro, 48)
        self.client.force_login(self.operador)
        self.client.post(reverse('deletar_reserva', args=[reserva.id]))
        self.client.force_login(self.usuario)
        dados = {'sala': self.sala.id, 'data_inicio': self.local(reserva.data_inicio),
                 'data_fim': self.local(reserva.data_fim), 'descricao': '', 'recorrencia': ''}
        self.assertEqual(self.client.post(reverse('criar_reserva'), dados).status_code, 302)

    def test_nome_de_sala_excluida_pode_ser_usado_de_novo(self):
        self.client.force_login(self.operador)
        self.client.post(reverse('deletar_sala', args=[self.sala.id]))
        dados = {'nome': self.sala.nome, 'capacidade': 8, 'descricao': ''} | RecursosTest.gestao(0)
        self.assertEqual(self.client.post(reverse('criar_sala'), dados).status_code, 302)
        self.assertEqual(Sala.todos.filter(nome=self.sala.nome, organizacao=self.org_a).count(), 2)

    def test_delete_da_api_tambem_so_marca(self):
        reserva = self.reserva(self.usuario, 48)
        api = APIClient()
        api.force_authenticate(self.operador)
        self.assertEqual(api.delete(f'/api/reservas/{reserva.id}/').status_code, 204)
        self.assertEqual(Reserva.todos.get(id=reserva.id).excluida_por, self.operador)
        self.assertEqual(api.delete(f'/api/salas/{self.sala_aprov.id}/').status_code, 204)
        self.assertEqual(Sala.todos.get(id=self.sala_aprov.id).excluida_por, self.operador)


class AdminExclusaoTest(Base):
    def setUp(self):
        self.chefe = User.objects.create_superuser('chefe', password='x')

    def test_admin_mostra_excluidas_e_restaura(self):
        reserva = self.reserva(self.usuario, 48)
        reserva.excluir(self.operador)
        self.sala_aprov.excluir(self.operador)
        self.client.force_login(self.chefe)
        resp = self.client.get('/admin/salas/reserva/', {'excluida': 'sim'})
        self.assertEqual(resp.context['cl'].result_count, 1)
        self.assertContains(resp, 'Excluída em')
        self.assertContains(resp, 'Excluída por')
        self.assertEqual(self.client.get('/admin/salas/reserva/', {'excluida': 'nao'}).context['cl'].result_count, 0)
        self.client.post('/admin/salas/reserva/', {'action': 'restaurar_selecionadas', '_selected_action': [reserva.id]})
        self.client.post('/admin/salas/sala/', {'action': 'restaurar_selecionadas', '_selected_action': [self.sala_aprov.id]})
        reserva.refresh_from_db()
        self.assertIsNone(reserva.excluida_em)
        self.assertIsNone(reserva.excluida_por)
        self.assertTrue(Reserva.objects.filter(id=reserva.id).exists())
        self.assertTrue(Sala.objects.filter(id=self.sala_aprov.id).exists())

    def test_restaurar_nao_cria_conflito(self):
        antiga = self.reserva(self.usuario, 48)
        antiga.excluir(self.operador)
        Reserva.objects.create(organizacao=self.org_a, sala=self.sala, responsavel='x', criado_por=self.outro,
                               data_inicio=antiga.data_inicio, data_fim=antiga.data_fim, status='confirmada')
        self.client.force_login(self.chefe)
        self.client.post('/admin/salas/reserva/', {'action': 'restaurar_selecionadas', '_selected_action': [antiga.id]})
        self.assertIsNotNone(Reserva.todos.get(id=antiga.id).excluida_em)

    def test_admin_apaga_de_vez(self):
        reserva = self.reserva(self.usuario, 48)
        reserva.excluir(self.operador)
        self.client.force_login(self.chefe)
        self.client.post(f'/admin/salas/reserva/{reserva.id}/delete/', {'post': 'yes'})
        self.assertFalse(Reserva.todos.filter(id=reserva.id).exists())


# ===== REGISTRO DE ATIVIDADES =====

class RegistroAtividadeTest(Base):
    def acoes(self, tipo):
        return list(RegistroAtividade.objects.filter(tipo_objeto=tipo).order_by('id').values_list('acao', flat=True))

    def test_cada_acao_do_site_gera_registro(self):
        # Reservas: criar, editar, cancelar
        self.client.force_login(self.usuario)
        self.client.post(reverse('criar_reserva'), self.dados_form(self.sala, 48))
        reserva = Reserva.objects.get()
        self.client.post(reverse('editar_reserva', args=[reserva.id]), self.dados_form(self.sala, 50))
        self.client.post(reverse('cancelar_reserva', args=[reserva.id]))
        # Aprovar, recusar e excluir
        self.client.post(reverse('criar_reserva'), self.dados_form(self.sala_aprov, 72))
        self.client.post(reverse('criar_reserva'), self.dados_form(self.sala_aprov, 96))
        pendente1, pendente2 = Reserva.objects.filter(status='pendente').order_by('data_inicio')
        self.client.force_login(self.operador)
        self.client.post(reverse('aprovar_reserva', args=[pendente1.id]))
        self.client.post(reverse('recusar_reserva', args=[pendente2.id]))
        self.client.post(reverse('deletar_reserva', args=[pendente1.id]))
        self.assertEqual(self.acoes('reserva'),
                         ['criou', 'editou', 'cancelou', 'criou', 'criou', 'aprovou', 'recusou', 'excluiu'])
        # Salas e recursos
        dados = {'nome': 'Lab', 'capacidade': 10, 'descricao': ''} | RecursosTest.gestao(2) | {
            'recursos-0-nome': 'Projetor', 'recursos-0-descricao': '',
            'recursos-1-nome': 'TV', 'recursos-1-descricao': '',
        }
        self.client.post(reverse('criar_sala'), dados)
        lab = Sala.objects.get(nome='Lab')
        projetor, tv = lab.recursos.order_by('id')
        dados = {'nome': 'Lab 2', 'capacidade': 10, 'descricao': ''} | RecursosTest.gestao(2, 2) | {
            'recursos-0-id': projetor.id, 'recursos-0-nome': 'Projetor 4K', 'recursos-0-descricao': '',
            'recursos-1-id': tv.id, 'recursos-1-nome': 'TV', 'recursos-1-descricao': '', 'recursos-1-DELETE': 'on',
        }
        self.client.post(reverse('editar_sala', args=[lab.id]), dados)
        self.client.post(reverse('deletar_sala', args=[lab.id]))
        self.assertEqual(self.acoes('sala'), ['criou', 'editou', 'excluiu'])
        self.assertEqual(self.acoes('recurso'), ['adicionou', 'adicionou', 'editou', 'removeu'])
        # Todos têm usuário, organização e descrição legível
        for registro in RegistroAtividade.objects.all():
            self.assertIsNotNone(registro.usuario)
            self.assertEqual(registro.organizacao, self.org_a)
            self.assertTrue(registro.descricao.startswith(registro.usuario.username + ' '))
        quando = timezone.localtime(Reserva.todos.get(id=reserva.id).data_inicio).strftime('%d/%m/%Y %H:%M')
        cancelou = RegistroAtividade.objects.get(acao='cancelou')
        self.assertEqual(cancelou.descricao, f'usuario cancelou a reserva da Sala 1 de {quando}')
        self.assertEqual(cancelou.objeto_id, reserva.id)
        self.assertEqual(RegistroAtividade.objects.get(acao='removeu').descricao, 'operador removeu o recurso TV na sala Lab 2')

    def test_api_gera_registro(self):
        api = APIClient()
        api.force_authenticate(self.usuario)
        inicio = timezone.now() + timedelta(hours=48)
        resp = api.post('/api/reservas/', {'sala': self.sala.id, 'data_inicio': inicio.isoformat(),
                                            'data_fim': (inicio + timedelta(hours=1)).isoformat()})
        id_ = resp.data['id']
        api.patch(f'/api/reservas/{id_}/', {'descricao': 'Nova'})
        api.post(f'/api/reservas/{id_}/cancelar/')
        api.force_authenticate(self.operador)
        api.delete(f'/api/reservas/{id_}/')
        resp = api.post('/api/salas/', {'nome': 'Sala API', 'capacidade': 4})
        api.post('/api/recursos/', {'sala': resp.data['id'], 'nome': 'Lousa'})
        self.assertEqual(self.acoes('reserva'), ['criou', 'editou', 'cancelou', 'excluiu'])
        self.assertEqual(self.acoes('sala'), ['criou'])
        self.assertEqual(self.acoes('recurso'), ['adicionou'])

    def test_cadastro_publico_gera_registro(self):
        self.client.post('/contas/cadastro/', {
            'username': 'novo', 'email': 'novo@example.com', 'password1': 'Senha-Forte-987',
            'password2': 'Senha-Forte-987', 'organizacao': self.org_b.id,
        })
        registro = RegistroAtividade.objects.get(acao='cadastrou')
        self.assertEqual(registro.usuario.username, 'novo')
        self.assertEqual(registro.organizacao, self.org_b)
        self.assertEqual(registro.descricao, 'novo criou a própria conta na organização Org B')

    def test_registro_e_somente_leitura_no_admin(self):
        registro = RegistroAtividade.objects.create(usuario=self.usuario, organizacao=self.org_a,
                                                    acao='criou', tipo_objeto='reserva', descricao='teste')
        chefe = User.objects.create_superuser('chefe', password='x')
        self.client.force_login(chefe)
        base = '/admin/core/registroatividade/'
        lista = self.client.get(base)
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, 'teste')
        self.assertEqual(self.client.get(base + 'add/').status_code, 403)
        alterar = self.client.get(f'{base}{registro.id}/change/')
        self.assertNotContains(alterar, 'name="_save"')
        self.assertEqual(self.client.post(f'{base}{registro.id}/change/', {'descricao': 'mudou'}).status_code, 403)
        registro.refresh_from_db()
        self.assertEqual(registro.descricao, 'teste')
        # Busca e filtros
        self.assertEqual(self.client.get(base, {'q': 'teste'}).context['cl'].result_count, 1)
        self.assertEqual(self.client.get(base, {'acao__exact': 'criou'}).context['cl'].result_count, 1)
        # Só o superusuário apaga
        self.client.post(f'{base}{registro.id}/delete/', {'post': 'yes'})
        self.assertFalse(RegistroAtividade.objects.filter(id=registro.id).exists())


# ===== PÁGINA DE DETALHES DA SALA =====

class DetalhesSalaTest(Base):
    def test_usuario_ve_recursos_e_proximas_reservas(self):
        Recurso.objects.create(organizacao=self.org_a, sala=self.sala, nome='Projetor', descricao='Full HD')
        futura = self.reserva(self.outro, 30)
        pendente = self.reserva(self.outro, 60, status='pendente')
        cancelada = self.reserva(self.outro, 90, status='cancelada')
        passada = self.reserva(self.outro, -30)
        excluida = self.reserva(self.outro, 120)
        excluida.excluir(self.operador)
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('detalhes_sala', args=[self.sala.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Sala 1')
        self.assertContains(resp, '10 pessoas')
        self.assertContains(resp, 'Projetor')
        self.assertContains(resp, 'Full HD')
        self.assertEqual(list(resp.context['proximas']), [futura, pendente])
        self.assertContains(resp, 'outro · sem e-mail')
        self.assertContains(resp, timezone.localtime(futura.data_inicio).strftime('%d/%m/%Y'))
        for fora in [cancelada, passada, excluida]:
            self.assertNotIn(fora, resp.context['proximas'])
        # Usuário comum não vê Editar nem Deletar
        self.assertNotContains(resp, reverse('editar_sala', args=[self.sala.id]))
        self.assertNotContains(resp, reverse('deletar_sala', args=[self.sala.id]))

    def test_funcionario_ve_editar_e_deletar(self):
        self.client.force_login(self.operador)
        resp = self.client.get(reverse('detalhes_sala', args=[self.sala.id]))
        self.assertContains(resp, reverse('editar_sala', args=[self.sala.id]))
        self.assertContains(resp, reverse('deletar_sala', args=[self.sala.id]))
        self.assertContains(resp, 'Exige aprovação' if self.sala.exige_aprovacao else 'Confirmação automática')

    def test_reservar_esta_sala_ja_traz_a_sala(self):
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('detalhes_sala', args=[self.sala_aprov.id]))
        url = f"{reverse('criar_reserva')}?sala={self.sala_aprov.id}"
        self.assertContains(resp, f'href="{url}"')
        form = self.client.get(url).context['form']
        self.assertEqual(form['sala'].value(), self.sala_aprov.id)
        # Sala de outra organização não é pré-selecionada
        form = self.client.get(f"{reverse('criar_reserva')}?sala={self.sala_b.id}").context['form']
        self.assertIsNone(form['sala'].value())

    def test_outra_organizacao_recebe_404(self):
        self.client.force_login(self.usuario_b)
        self.assertEqual(self.client.get(reverse('detalhes_sala', args=[self.sala.id])).status_code, 404)
        self.client.force_login(self.operador)
        self.assertEqual(self.client.get(reverse('detalhes_sala', args=[self.sala_b.id])).status_code, 404)

    def test_sala_excluida_recebe_404(self):
        self.sala.excluir(self.operador)
        self.client.force_login(self.operador)
        self.assertEqual(self.client.get(reverse('detalhes_sala', args=[self.sala.id])).status_code, 404)

    def test_lista_de_salas_abre_a_pagina_e_mantem_os_botoes(self):
        self.client.force_login(self.operador)
        resp = self.client.get(reverse('lista_salas'))
        for sala in [self.sala, self.sala_aprov]:
            self.assertContains(resp, f'href="{reverse("detalhes_sala", args=[sala.id])}" class="link-sala stretched-link"')
            self.assertContains(resp, reverse('editar_sala', args=[sala.id]))
            self.assertContains(resp, reverse('deletar_sala', args=[sala.id]))
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get(reverse('lista_salas')), reverse('detalhes_sala', args=[self.sala.id]))


# ===== RESERVAS RECORRENTES =====

class RecorrenciaTest(Base):
    @staticmethod
    def inicio(dias=2, hora=10):
        local = timezone.localtime(timezone.now()) + timedelta(days=dias)
        return local.replace(hour=hora, minute=0, second=0, microsecond=0)

    @staticmethod
    def dados_serie(sala, inicio, repetir='semanal', a_cada=1, ate=None, horas=1):
        formato = '%Y-%m-%dT%H:%M'
        return {
            'sala': sala.id, 'descricao': 'Aula',
            'data_inicio': inicio.strftime(formato),
            'data_fim': (inicio + timedelta(hours=horas)).strftime(formato),
            'repetir': repetir, 'a_cada': a_cada, 'ate': ate.isoformat() if ate else '',
        }

    def cria_serie(self, user, sala=None, inicio=None, semanas=4, **extra):
        inicio = inicio or self.inicio()
        ate = (inicio + timedelta(weeks=semanas - 1)).date()
        self.client.force_login(user)
        return self.client.post(reverse('criar_reserva'), self.dados_serie(sala or self.sala, inicio, ate=ate, **extra),
                                follow=True)

    def test_serie_semanal_de_4_semanas(self):
        inicio = self.inicio()
        resp = self.cria_serie(self.usuario, inicio=inicio)
        reservas = list(Reserva.objects.order_by('data_inicio'))
        self.assertEqual(len(reservas), 4)
        serie = reservas[0].recorrencia
        self.assertIsNotNone(serie)
        self.assertEqual((serie.frequencia, serie.intervalo, serie.organizacao), ('semanal', 1, self.org_a))
        for n, reserva in enumerate(reservas):
            self.assertEqual(reserva.recorrencia, serie)
            self.assertEqual(timezone.localtime(reserva.data_inicio), inicio + timedelta(weeks=n))
            self.assertEqual(reserva.data_fim - reserva.data_inicio, timedelta(hours=1))
            self.assertEqual((reserva.sala, reserva.criado_por, reserva.status), (self.sala, self.usuario, 'confirmada'))
        primeira, ultima = inicio.strftime('%d/%m'), (inicio + timedelta(weeks=3)).strftime('%d/%m')
        self.assertContains(resp, f'Série criada: 4 reservas de {primeira} a {ultima}')
        # Etiqueta na lista e nos detalhes
        rotulo = f"Recorrente (semanal, a cada 1, até {serie.data_fim.strftime('%d/%m')})"
        self.assertContains(self.client.get(reverse('lista_reservas')), rotulo)
        self.assertContains(self.client.get(reverse('detalhes_reserva', args=[reservas[2].id])), rotulo)
        # Histórico
        registro = RegistroAtividade.objects.get(tipo_objeto='recorrência')
        self.assertEqual((registro.acao, registro.usuario, registro.objeto_id), ('criou', self.usuario, serie.id))
        self.assertIn('criou uma série de 4 reservas da Sala 1', registro.descricao)

    def test_sala_com_aprovacao_cria_serie_pendente(self):
        resp = self.cria_serie(self.usuario, sala=self.sala_aprov, semanas=3)
        self.assertEqual(set(Reserva.objects.values_list('status', flat=True)), {'pendente'})
        self.assertContains(resp, 'aguardam a aprovação')

    def test_a_cada_2_semanas_e_mensal_no_fim_do_mes(self):
        inicio = self.inicio()
        self.client.force_login(self.usuario)
        self.client.post(reverse('criar_reserva'),
                         self.dados_serie(self.sala, inicio, a_cada=2, ate=(inicio + timedelta(weeks=5)).date()))
        datas = [timezone.localtime(r.data_inicio) for r in Reserva.objects.order_by('data_inicio')]
        self.assertEqual(datas, [inicio, inicio + timedelta(weeks=2), inicio + timedelta(weeks=4)])
        Reserva.objects.all().delete()
        # 31/01 do ano que vem vira 28/02 (ou 29), 31/03, 30/04
        ano = timezone.localtime(timezone.now()).year + 1
        jan = timezone.make_aware(timezone.datetime(ano, 1, 31, 9, 0))
        self.client.post(reverse('criar_reserva'),
                         self.dados_serie(self.sala, timezone.localtime(jan), repetir='mensal',
                                          ate=timezone.datetime(ano, 4, 30).date()))
        dias = [timezone.localtime(r.data_inicio).strftime('%d/%m') for r in Reserva.objects.order_by('data_inicio')]
        fim_fev = calendar.monthrange(ano, 2)[1]
        self.assertEqual(dias, ['31/01', f'{fim_fev}/02', '31/03', '30/04'])

    def test_conflito_em_uma_data_bloqueia_a_serie(self):
        inicio = self.inicio()
        ocupada = inicio + timedelta(weeks=2)
        Reserva.objects.create(organizacao=self.org_a, sala=self.sala, responsavel='x', criado_por=self.outro,
                               data_inicio=ocupada, data_fim=ocupada + timedelta(hours=1), status='confirmada')
        resp = self.cria_serie(self.usuario, inicio=inicio)
        self.assertEqual(Reserva.objects.count(), 1)
        self.assertFalse(Reserva.objects.filter(recorrencia__isnull=False).exists())
        self.assertContains(resp, 'Conflito! Estas datas já estão ocupadas nesta sala')
        self.assertContains(resp, ocupada.strftime('%d/%m/%Y %H:%M'))
        self.assertFalse(RegistroAtividade.objects.filter(tipo_objeto='recorrência').exists())

    def test_validacoes_do_ate(self):
        inicio = self.inicio(dias=10)
        self.client.force_login(self.usuario)
        casos = [
            ((inicio - timedelta(days=1)).date(), 'não pode ser antes do início'),
            (None, 'Informe até quando'),
            ((inicio + timedelta(days=400)).date(), 'no máximo 1 ano'),
        ]
        for ate, mensagem in casos:
            resp = self.client.post(reverse('criar_reserva'), self.dados_serie(self.sala, inicio, ate=ate))
            self.assertEqual(resp.status_code, 200)
            self.assertIn(mensagem, str(resp.context['form'].errors.get('ate')))
        # Todo dia por quase 1 ano passa de 100 reservas
        resp = self.client.post(reverse('criar_reserva'),
                                self.dados_serie(self.sala, inicio, repetir='diaria', ate=(inicio + timedelta(days=200)).date()))
        self.assertContains(resp, 'passaria de 100 reservas')
        self.assertFalse(Reserva.objects.exists())

    def test_nao_repetir_cria_uma_so(self):
        self.client.force_login(self.usuario)
        dados = self.dados_serie(self.sala, self.inicio(), repetir='nao', ate=(self.inicio() + timedelta(weeks=3)).date())
        self.assertEqual(self.client.post(reverse('criar_reserva'), dados).status_code, 302)
        self.assertEqual(Reserva.objects.count(), 1)
        self.assertIsNone(Reserva.objects.get().recorrencia)

    def test_datas_no_passado_nao_sao_criadas(self):
        inicio = self.inicio(dias=-3)
        self.cria_serie(self.usuario, inicio=inicio, semanas=4)
        datas = [timezone.localtime(r.data_inicio) for r in Reserva.objects.order_by('data_inicio')]
        self.assertEqual(datas, [inicio + timedelta(weeks=n) for n in (1, 2, 3)])

    def test_cancelar_esta_e_as_proximas_respeita_24h(self):
        perto = timezone.localtime(timezone.now() + timedelta(hours=5)).replace(minute=0, second=0, microsecond=0)
        self.cria_serie(self.usuario, inicio=perto)
        primeira = Reserva.objects.order_by('data_inicio').first()
        resp = self.client.post(reverse('cancelar_serie', args=[primeira.id]), follow=True)
        status = list(Reserva.objects.order_by('data_inicio').values_list('status', flat=True))
        self.assertEqual(status, ['confirmada', 'cancelada', 'cancelada', 'cancelada'])
        self.assertContains(resp, '3 reserva(s) da série cancelada(s). 1 ficaram ativas')
        registro = RegistroAtividade.objects.get(tipo_objeto='recorrência', acao='cancelou')
        self.assertIn('cancelou 3 reservas da série da Sala 1', registro.descricao)

    def test_cancelar_a_partir_do_meio_nao_mexe_nas_anteriores(self):
        perto = timezone.localtime(timezone.now() + timedelta(hours=5)).replace(minute=0, second=0, microsecond=0)
        self.cria_serie(self.usuario, inicio=perto)
        reservas = list(Reserva.objects.order_by('data_inicio'))
        # Operador cancela a partir da terceira; a primeira (menos de 24h) e a segunda ficam
        self.client.force_login(self.operador)
        self.client.post(reverse('cancelar_serie', args=[reservas[2].id]))
        status = list(Reserva.objects.order_by('data_inicio').values_list('status', flat=True))
        self.assertEqual(status, ['confirmada', 'confirmada', 'cancelada', 'cancelada'])
        # Operador pode cancelar mesmo com menos de 24h
        self.client.post(reverse('cancelar_serie', args=[reservas[0].id]))
        self.assertEqual(set(Reserva.objects.values_list('status', flat=True)), {'cancelada'})

    def test_cada_reserva_da_serie_cancela_sozinha_e_edita_so_ela(self):
        self.cria_serie(self.usuario)
        reservas = list(Reserva.objects.order_by('data_inicio'))
        self.client.post(reverse('cancelar_reserva', args=[reservas[1].id]))
        status = list(Reserva.objects.order_by('data_inicio').values_list('status', flat=True))
        self.assertEqual(status, ['confirmada', 'cancelada', 'confirmada', 'confirmada'])
        # Edição: sem campos de repetição e a recorrência não muda
        form = self.client.get(reverse('editar_reserva', args=[reservas[3].id])).context['form']
        self.assertNotIn('repetir', form.fields)
        nova = reservas[3].data_inicio + timedelta(hours=2)
        dados = {'sala': self.sala.id, 'descricao': 'Mudou', 'data_inicio': self.local(nova),
                 'data_fim': self.local(nova + timedelta(hours=1))}
        self.client.post(reverse('editar_reserva', args=[reservas[3].id]), dados)
        reservas[3].refresh_from_db()
        self.assertEqual(reservas[3].recorrencia, reservas[0].recorrencia)
        self.assertEqual(reservas[3].descricao, 'Mudou')
        self.assertEqual(Reserva.objects.filter(descricao='Mudou').count(), 1)

    def test_outra_pessoa_e_outra_organizacao(self):
        self.cria_serie(self.usuario)
        primeira = Reserva.objects.order_by('data_inicio').first()
        self.client.force_login(self.outro)
        self.assertEqual(self.client.post(reverse('cancelar_serie', args=[primeira.id])).status_code, 403)
        self.client.force_login(self.usuario_b)
        self.assertEqual(self.client.post(reverse('cancelar_serie', args=[primeira.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse('detalhes_reserva', args=[primeira.id])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('lista_reservas')), 'Recorrente')
        api = APIClient()
        api.force_authenticate(self.usuario_b)
        self.assertEqual(api.get('/api/reservas/').data, [])
        self.assertEqual(set(Reserva.objects.values_list('status', flat=True)), {'confirmada'})

    def test_serie_pela_api(self):
        api = APIClient()
        api.force_authenticate(self.usuario)
        inicio = self.inicio()
        dados = {'sala': self.sala.id, 'data_inicio': inicio.isoformat(),
                 'data_fim': (inicio + timedelta(hours=1)).isoformat(),
                 'repetir': 'semanal', 'a_cada': 1, 'ate': (inicio + timedelta(weeks=3)).date().isoformat()}
        resp = api.post('/api/reservas/', dados, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['total'], 4)
        ids = {r['recorrencia'] for r in resp.data['reservas']}
        self.assertEqual(ids, {resp.data['recorrencia']})
        self.assertEqual(Reserva.objects.filter(recorrencia_id=resp.data['recorrencia'], criado_por=self.usuario).count(), 4)
        # A mesma série de novo: todas as datas conflitam
        resp = api.post('/api/reservas/', dados, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn(inicio.strftime('%d/%m/%Y %H:%M'), str(resp.data))
        # "Até" antes do início
        resp = api.post('/api/reservas/', dados | {'ate': (inicio - timedelta(days=1)).date().isoformat()}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ate', resp.data)
        # Sem repetir continua criando uma reserva só
        outra = inicio + timedelta(days=1)
        resp = api.post('/api/reservas/', {'sala': self.sala.id, 'data_inicio': outra.isoformat(),
                                           'data_fim': (outra + timedelta(hours=1)).isoformat()}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(resp.data['recorrencia'])
        # PATCH não muda a recorrência
        primeira = Reserva.objects.filter(recorrencia__isnull=False).order_by('data_inicio').first()
        api.patch(f'/api/reservas/{primeira.id}/', {'recorrencia': None, 'repetir': 'diaria', 'descricao': 'x'}, format='json')
        primeira.refresh_from_db()
        self.assertIsNotNone(primeira.recorrencia)
        self.assertEqual(Reserva.objects.count(), 5)

    def test_formulario_mostra_os_campos_de_repeticao(self):
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('criar_reserva'))
        for campo in ['name="repetir"', 'name="a_cada"', 'name="ate"', 'Não repetir', 'Todo dia', 'Toda semana', 'Todo mês']:
            self.assertContains(resp, campo)
        self.assertNotContains(resp, 'name="recorrencia"')
