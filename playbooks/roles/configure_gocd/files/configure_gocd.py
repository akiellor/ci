#!/usr/bin/env python
from gomatic import *
import os

def _create_pipeline(group, pipeline_name, add_cf_vars=False):
	pipeline_group = configurator.ensure_pipeline_group(group)
	pipeline = pipeline_group.ensure_replacement_of_pipeline(pipeline_name)
	if(add_cf_vars == True):
		pipeline.ensure_unencrypted_secure_environment_variables({"CF_USERNAME": os.environ['CF_USERNAME'], "CF_PASSWORD": os.environ['CF_PASSWORD']})
		pipeline.ensure_environment_variables({"CF_HOME": "."})
	return pipeline

def _add_exec_task(job, command, working_dir=None, runif="passed"):
	job.add_task(ExecTask(['/bin/bash', '-l', '-c', command], working_dir=working_dir, runif=runif))

def build_catalog_pipeline_group(configurator):
	pipeline = _create_pipeline("catalog", "catalog_unit_tests")
	pipeline.set_git_url("https://github.com/ThoughtWorks-AELab/pretend_catalog_service")
	job = pipeline.ensure_stage("test").ensure_job("test")
	_add_exec_task(job, 'bundle install --path vendor/bundle --without production')
	_add_exec_task(job, 'bundle exec rake assemble')
	_add_exec_task(job, 'bundle exec rake spec:unit')
	job.ensure_artifacts({TestArtifact("build/test-results")})
	job.ensure_artifacts({BuildArtifact("*", "catalog_build")})

	pipeline = _create_pipeline("catalog", "catalog_functional_tests", True)
	pipeline.ensure_material(PipelineMaterial('catalog_unit_tests', 'test'))
	job = pipeline.ensure_stage("test").ensure_job("test")
	job.add_task(FetchArtifactTask('catalog_unit_tests', 'test', 'test', FetchArtifactDir('catalog_build')))
	_add_exec_task(job, 'bundle exec rake cf:deploy[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER]', 'catalog_build')
	_add_exec_task(job, 'BASE_URL=http://$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER-catalog.cfapps.io bundle exec rake spec:functional', 'catalog_build')
	_add_exec_task(job, 'bundle exec rake cf:delete[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER]', 'catalog_build', runif='any')
	job.ensure_artifacts(set([BuildArtifact("catalog_build/*", "catalog_build"), TestArtifact("catalog_build/spec/reports")]))

	pipeline = _create_pipeline("catalog", "catalog_deployment", True)
	pipeline.ensure_material(PipelineMaterial('catalog_functional_tests', 'test'))
	stage = pipeline.ensure_stage("Deploy_Staging")
	job = stage.ensure_job("deploy")
	job.add_task(FetchArtifactTask('catalog_functional_tests', 'test', 'test', FetchArtifactDir('catalog_build')))
	_add_exec_task(job, 'bundle exec rake cf:deploy[staging,staging]', 'catalog_build')
	stage = pipeline.ensure_stage("Deploy_Production")
	stage.set_has_manual_approval()
	job = stage.ensure_job("deploy")
	job.add_task(FetchArtifactTask('catalog_functional_tests', 'test', 'test', FetchArtifactDir('catalog_build')))
	_add_exec_task(job, 'bundle exec rake cf:deploy[production]', 'catalog_build')

def build_pricing_pipeline_group(configurator):
	pipeline = _create_pipeline("pricing", "pricing_unit_tests")
	pipeline.set_git_url("https://github.com/ThoughtWorks-AELab/pretend_pricing_service")
	job = pipeline.ensure_stage("test").ensure_job("test")
	_add_exec_task(job, 'bundle install --path vendor/bundle')
	_add_exec_task(job, 'bundle exec rake db:migrate')
	_add_exec_task(job, 'bundle exec rake spec:unit')
	job.ensure_artifacts({TestArtifact("spec/reports")})
	job.ensure_artifacts({BuildArtifact("*", "pricing_build")})

	pipeline = _create_pipeline("pricing", "pricing_functional_tests", True)
	pipeline.ensure_material(PipelineMaterial('pricing_unit_tests', 'test'))
	job = pipeline.ensure_stage("test").ensure_job("test")
	job.add_task(FetchArtifactTask('pricing_unit_tests', 'test', 'test', FetchArtifactDir('pricing_build')))
	_add_exec_task(job, 'PREFIX=$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER bundle exec rake spec:functional', 'pricing_build')
	job.ensure_artifacts(set([BuildArtifact("pricing_build/*", "pricing_build"), TestArtifact("pricing_build/spec/reports")]))

	pipeline = _create_pipeline("pricing", "pricing_deployment", True)
	pipeline.ensure_material(PipelineMaterial('pricing_functional_tests', 'test'))
	stage = pipeline.ensure_stage("Deploy_Staging")
	job = stage.ensure_job("deploy")
	job.add_task(FetchArtifactTask('pricing_functional_tests', 'test', 'test', FetchArtifactDir('pricing_build')))
	_add_exec_task(job, 'bundle exec rake cf:deploy[staging,staging]', 'pricing_build')
	stage = pipeline.ensure_stage("Deploy_Production")
	stage.set_has_manual_approval()
	job = stage.ensure_job("deploy")
	job.add_task(FetchArtifactTask('pricing_functional_tests', 'test', 'test', FetchArtifactDir('pricing_build')))
	_add_exec_task(job, 'bundle exec rake cf:deploy[production]', 'pricing_build')

def build_deals_pipeline_group(configurator):
	pipeline = _create_pipeline("deals", "deals_unit_tests")
	pipeline.set_git_url("https://github.com/ThoughtWorks-AELab/pretend_deals_service")
	job = pipeline.ensure_stage("test").ensure_job("test")
	_add_exec_task(job, 'bundle install --path vendor/bundle --without production')
	_add_exec_task(job, 'bundle exec rake spec:unit')
	job.ensure_artifacts({TestArtifact("spec/reports")})
	job.ensure_artifacts({BuildArtifact("*", "deals_build")})

	pipeline = _create_pipeline("deals", "deals_functional_tests", True)
	pipeline.ensure_material(PipelineMaterial('pricing_functional_tests', 'test', 'pricing_functional_tests'))
	pipeline.ensure_material(PipelineMaterial('deals_unit_tests', 'test'))
	job = pipeline.ensure_stage("test").ensure_job("test")
	job.add_task(FetchArtifactTask('pricing_functional_tests', 'test', 'test', FetchArtifactDir('pricing_build')))
	job.add_task(FetchArtifactTask('deals_unit_tests', 'test', 'test', FetchArtifactDir('deals_build')))
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:cups[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: pricing_build deals_build')
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:deploy[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: pricing_build deals_build')
	_add_exec_task(job, 'BASE_URL=http://$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER-deals.cfapps.io bundle exec rake spec:functional', 'deals_build')
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:delete[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: pricing_build deals_build', runif='any')
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:dups[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: pricing_build deals_build', runif='any')
	job.ensure_artifacts(set([BuildArtifact("deals_build/*", "deals_build"), BuildArtifact("pricing_build/*", "pricing_build"), TestArtifact("deals_build/spec/reports")]))

	pipeline = _create_pipeline("deals", "deals_deployment", True)
	pipeline.ensure_material(PipelineMaterial('deals_functional_tests', 'test'))
	stage = pipeline.ensure_stage("Deploy_Staging")
	job = stage.ensure_job("deploy")
	job.add_task(FetchArtifactTask('deals_functional_tests', 'test', 'test', FetchArtifactDir('deals_build')))
	_add_exec_task(job, 'bundle exec rake cf:deploy[staging,staging]', 'deals_build')
	stage = pipeline.ensure_stage("Deploy_Production")
	stage.set_has_manual_approval()
	job = stage.ensure_job("deploy")
	job.add_task(FetchArtifactTask('deals_functional_tests', 'test', 'test', FetchArtifactDir('deals_build')))
	_add_exec_task(job, 'bundle exec rake cf:deploy[production]', 'deals_build')

def build_web_app_pipeline_group(configurator):
	pipeline = _create_pipeline("web_app", "web_app_unit_tests", True)
	pipeline.set_git_url("https://github.com/ThoughtWorks-AELab/pretend_web_app")
	job = pipeline.ensure_stage("test").ensure_job("test")
	_add_exec_task(job, 'bundle install --path vendor/bundle --without production')
	_add_exec_task(job, 'bundle exec rake spec:unit')
	job.ensure_artifacts({TestArtifact("spec/reports")})
	job.ensure_artifacts({BuildArtifact("*", "web_app_build")})

	pipeline = _create_pipeline("web_app", "web_app_functional_tests", True)
	pipeline.ensure_material(PipelineMaterial('catalog_functional_tests', 'test', 'catalog_functional_tests'))
	pipeline.ensure_material(PipelineMaterial('deals_functional_tests', 'test', 'deals_functional_tests'))
	pipeline.ensure_material(PipelineMaterial('web_app_unit_tests', 'test'))
	job = pipeline.ensure_stage("test").ensure_job("test")
	job.add_task(FetchArtifactTask('catalog_functional_tests', 'test', 'test', FetchArtifactDir('catalog_build')))
	job.add_task(FetchArtifactTask('deals_functional_tests', 'test', 'test', FetchArtifactDir('pricing_build')))
	job.add_task(FetchArtifactTask('deals_functional_tests', 'test', 'test', FetchArtifactDir('deals_build')))
	job.add_task(FetchArtifactTask('web_app_unit_tests', 'test', 'test', FetchArtifactDir('web_app_build')))
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:cups[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: catalog_build pricing_build deals_build web_app_build')
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:deploy[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: catalog_build pricing_build deals_build web_app_build')
	_add_exec_task(job, 'BASE_URL=http://$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER-web-app.cfapps.io bundle exec rake spec:functional', 'web_app_build')
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:delete[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: catalog_build pricing_build deals_build web_app_build', runif='any')
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:dups[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: catalog_build pricing_build deals_build web_app_build', runif='any')
	job.ensure_artifacts(set([BuildArtifact("catalog_build/*", "catalog_build"), BuildArtifact("pricing_build/*", "pricing_build"), BuildArtifact("deals_build/*", "deals_build"), BuildArtifact("web_app_build/*", "web_app_build"), TestArtifact("web_app_build/spec/reports")]))

	pipeline = _create_pipeline("web_app", "web_app_deployment", True)
	pipeline.ensure_material(PipelineMaterial('web_app_functional_tests', 'test'))
	stage = pipeline.ensure_stage("Deploy_Staging")
	job = stage.ensure_job("deploy")
	job.add_task(FetchArtifactTask('web_app_functional_tests', 'test', 'test', FetchArtifactDir('web_app_build')))
	_add_exec_task(job, 'bundle exec rake cf:deploy[staging,staging]', 'web_app_build')
	stage = pipeline.ensure_stage("Deploy_Production")
	stage.set_has_manual_approval()
	job = stage.ensure_job("deploy")
	job.add_task(FetchArtifactTask('web_app_functional_tests', 'test', 'test', FetchArtifactDir('web_app_build')))
	_add_exec_task(job, 'bundle exec rake cf:deploy[production]', 'web_app_build')

def build_pie_pipeline_group(configurator):
	pipeline = _create_pipeline("PIE", "PIE", True)
	pipeline.ensure_material(PipelineMaterial('web_app_functional_tests', 'test', 'web_app_functional_tests'))
	stage = pipeline.ensure_stage("deploy")
	stage.set_has_manual_approval()
	job = stage.ensure_job("deploy")
	job.add_task(FetchArtifactTask('web_app_functional_tests', 'test', 'test', FetchArtifactDir('catalog_build')))
	job.add_task(FetchArtifactTask('web_app_functional_tests', 'test', 'test', FetchArtifactDir('pricing_build')))
	job.add_task(FetchArtifactTask('web_app_functional_tests', 'test', 'test', FetchArtifactDir('deals_build')))
	job.add_task(FetchArtifactTask('web_app_functional_tests', 'test', 'test', FetchArtifactDir('web_app_build')))
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:cups[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: catalog_build pricing_build deals_build web_app_build')
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:deploy[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: catalog_build pricing_build deals_build web_app_build')
	stage = pipeline.ensure_stage("destroy")
	stage.set_has_manual_approval()
	job = stage.ensure_job("destroy")
	job.add_task(FetchArtifactTask('web_app_functional_tests', 'test', 'test', FetchArtifactDir('catalog_build')))
	job.add_task(FetchArtifactTask('web_app_functional_tests', 'test', 'test', FetchArtifactDir('pricing_build')))
	job.add_task(FetchArtifactTask('web_app_functional_tests', 'test', 'test', FetchArtifactDir('deals_build')))
	job.add_task(FetchArtifactTask('web_app_functional_tests', 'test', 'test', FetchArtifactDir('web_app_build')))
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:delete[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: catalog_build pricing_build deals_build web_app_build', runif='any')
	_add_exec_task(job, 'parallel "cd {}; bundle exec rake cf:dups[test,$GO_PIPELINE_NAME$GO_PIPELINE_COUNTER];" ::: catalog_build pricing_build deals_build web_app_build', runif='any')

configurator = GoCdConfigurator(HostRestClient("localhost:8153"))
configurator.remove_all_pipeline_groups()
build_catalog_pipeline_group(configurator)
build_pricing_pipeline_group(configurator)
build_deals_pipeline_group(configurator)
build_web_app_pipeline_group(configurator)
build_pie_pipeline_group(configurator)
configurator.save_updated_config()
