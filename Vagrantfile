# ──────────────────────────────────────────────────────────────────────────────
# Vagrantfile
# Spins up an Ubuntu 22.04 VM that mirrors a production environment.
# The VM runs Docker + Docker Compose to host the full application stack.
# ──────────────────────────────────────────────────────────────────────────────

Vagrant.configure("2") do |config|

  # ── Base box ────────────────────────────────────────────────────────────────
  # Ubuntu 22.04 LTS — same OS you'd use on a cloud VM (AWS/GCP/DigitalOcean)
  config.vm.box = "ubuntu/jammy64"
  config.vm.box_version = "~> 20240301.0.0"

  # ── Hostname ────────────────────────────────────────────────────────────────
  config.vm.hostname = "student-api-prod"

  # ── Network ─────────────────────────────────────────────────────────────────
  # Forward host port 8080 -> VM port 80 (Nginx)
  # Access the API on your laptop at http://localhost:8080
  config.vm.network "forwarded_port",
    guest: 80,
    host:  8080,
    host_ip: "127.0.0.1",
    auto_correct: true

  # Private network so the VM gets a stable IP
  config.vm.network "private_network", ip: "192.168.56.10"

  # ── Synced folder ───────────────────────────────────────────────────────────
  # Mounts the project root into /vagrant inside the VM.
  config.vm.synced_folder ".", "/vagrant",
    type: "virtualbox",
    owner: "vagrant",
    group: "vagrant"

  # ── VM resources ────────────────────────────────────────────────────────────
  config.vm.provider "virtualbox" do |vb|
    vb.name   = "student-api-prod"
    vb.memory = "2048"
    vb.cpus   = 2
  end

  # ── Provisioning ────────────────────────────────────────────────────────────
  config.vm.provision "shell",
    path: "scripts/provision.sh",
    privileged: true

  # ── Post-provision message ──────────────────────────────────────────────────
  config.vm.post_up_message = <<~MSG

    Student CRUD API is up!

    API (via Nginx):   http://localhost:8080/api/v1/students
    Healthcheck:       http://localhost:8080/healthcheck
    VM SSH:            vagrant ssh
    Stop VM:           vagrant halt
    Destroy VM:        vagrant destroy

  MSG

end